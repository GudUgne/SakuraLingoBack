from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):  # Extending Django's default user model
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    is_teacher = models.BooleanField(default=False)
    verification_status = models.BooleanField(default=False)  # Controlled by frontend

    def __str__(self):
        return self.username

class ExerciseMatch(models.Model):
    jlpt_level = models.IntegerField()

    def __str__(self):
        return f"Match Exercise Level {self.jlpt_level}"

    @property
    def is_library_pair(self):
        """Check if this is a single-pair library entry"""
        return self.exercisematchoptions_set.count() == 1

    @property
    def is_real_exercise(self):
        """Check if this is a real exercise with multiple pairs"""
        return self.exercisematchoptions_set.count() >= 2


class ExerciseFreetext(models.Model):
    question = models.TextField()
    answer = models.TextField()
    jlpt_level = models.IntegerField()

    def __str__(self):
        return self.question


class ExerciseMultiChoice(models.Model):
    question = models.TextField()
    jlpt_level = models.IntegerField()

    def __str__(self):
        return self.question


class ExerciseMultiChoiceOptions(models.Model):
    exercise_mc = models.ForeignKey(ExerciseMultiChoice, on_delete=models.CASCADE)
    answer = models.TextField()
    is_correct = models.BooleanField()

    def __str__(self):
        return self.answer


class ExerciseMatchOptions(models.Model):
    exercise_match = models.ForeignKey(ExerciseMatch, on_delete=models.CASCADE)
    kanji = models.TextField()
    answer = models.TextField()

    def __str__(self):
        return f"{self.kanji} - {self.answer}"


class Chat(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sender')
    # for 1:1
    receiver = models.ForeignKey(User, null=True, blank=True,
                                 on_delete = models.CASCADE, related_name = 'chat_receiver')
    # for class/group chats:
    group = models.ForeignKey('SakuraLingo.Group', null=True, blank=True,
                              on_delete=models.CASCADE, related_name='chat_group')
    message_content = models.TextField()
    is_group_message = models.BooleanField(default=False)
    time_sent = models.DateTimeField()

    def __str__(self):
        if self.is_group_message and self.group:
            return f"[Group:{self.group.name}] {self.sender.username}: {self.message_content}"
        elif self.receiver:
            return f"{self.sender.username} → {self.receiver.username}: {self.message_content}"
        return f"{self.sender.username}: {self.message_content}"


class Group(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name


class GroupsStudents(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    verification_status = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student.username} in {self.group.name}"

class Lesson(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    lesson_type = models.CharField(max_length=100, default='mixed')
    jlpt_level = models.CharField(max_length=10, default='1-5')
    exercise_count = models.IntegerField(default=0)

    def __str__(self):
        return self.name

    def update_lesson_stats(self):
        """Update lesson type and JLPT level based on exercises"""
        lesson_exercises = LessonsExercises.objects.filter(lesson=self)

        if not lesson_exercises.exists():
            self.lesson_type = 'empty'
            self.jlpt_level = 'unknown'
            self.exercise_count = 0
            self.save()
            return

        # Update exercise count
        self.exercise_count = lesson_exercises.count()

        # Determine lesson type
        exercise_types = set()
        jlpt_levels = set()

        for le in lesson_exercises:
            exercise_types.add(le.exercise_type)

            # Get JLPT level based on exercise type
            try:
                if le.exercise_type == 'freetext':
                    exercise = ExerciseFreetext.objects.get(id=le.exercise_id)
                    jlpt_levels.add(exercise.jlpt_level)
                elif le.exercise_type == 'multi-choice':
                    exercise = ExerciseMultiChoice.objects.get(id=le.exercise_id)
                    jlpt_levels.add(exercise.jlpt_level)
                elif le.exercise_type == 'pair-match':
                    exercise = ExerciseMatch.objects.get(id=le.exercise_id)
                    # Only include if it's a real exercise (not a library pair)
                    if exercise.is_real_exercise:
                        jlpt_levels.add(exercise.jlpt_level)
            except:
                # Exercise might be deleted, skip
                continue

        # Set lesson type
        if len(exercise_types) == 1:
            self.lesson_type = list(exercise_types)[0]
        else:
            self.lesson_type = 'mixed'

        # Set JLPT level range
        if jlpt_levels:
            min_level = min(jlpt_levels)
            max_level = max(jlpt_levels)
            if min_level == max_level:
                self.jlpt_level = str(min_level)
            else:
                self.jlpt_level = f"{min_level}-{max_level}"
        else:
            self.jlpt_level = 'unknown'

        self.save()

# Add these signal handlers to ensure proper cleanup
@receiver(post_delete, sender=ExerciseMatch)
def cleanup_lesson_exercises_on_match_delete(sender, instance, **kwargs):
    """Clean up lesson exercises when a match exercise is deleted"""
    LessonsExercises.objects.filter(
        exercise_type='pair-match',
        exercise_id=instance.id
    ).delete()

@receiver(post_delete, sender=ExerciseFreetext)
def cleanup_lesson_exercises_on_freetext_delete(sender, instance, **kwargs):
    """Clean up lesson exercises when a freetext exercise is deleted"""
    LessonsExercises.objects.filter(
        exercise_type='freetext',
        exercise_id=instance.id
    ).delete()

@receiver(post_delete, sender=ExerciseMultiChoice)
def cleanup_lesson_exercises_on_multichoice_delete(sender, instance, **kwargs):
    """Clean up lesson exercises when a multichoice exercise is deleted"""
    LessonsExercises.objects.filter(
        exercise_type='multi-choice',
        exercise_id=instance.id
    ).delete()


class LessonsExercises(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    exercise_id = models.IntegerField()  # Exercise ID can be from any of the exercise tables
    exercise_type = models.CharField(max_length=50)  # 'freetext', 'multi-choice', 'pair-match'

    class Meta:
        unique_together = ['lesson', 'exercise_id', 'exercise_type']  # Prevent duplicates

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update lesson stats when exercise is added
        self.lesson.update_lesson_stats()

    def delete(self, *args, **kwargs):
        lesson = self.lesson
        super().delete(*args, **kwargs)
        # Update lesson stats when exercise is removed
        lesson.update_lesson_stats()

    def __str__(self):
        return f"{self.lesson.name} - {self.exercise_id} ({self.exercise_type})"

class Homework(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='homework_teacher')
    group = models.ForeignKey('SakuraLingo.Group', on_delete=models.CASCADE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    def __str__(self):
        return f"Homework for {self.lesson.name}"


class HomeworkResult(models.Model):
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.IntegerField()

    def __str__(self):
        return f"Result for {self.student.username} - {self.homework.lesson.name}"