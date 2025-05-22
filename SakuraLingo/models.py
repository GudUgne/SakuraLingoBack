from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser


# class User(AbstractUser):
#     username = models.CharField(max_length=100, unique=True)
#     password = models.CharField(max_length=100)
#     email = models.EmailField(unique=True)
#     is_teacher = models.BooleanField(default=False)
#     verification_status = models.BooleanField(default=False)
#
#     def save(self, *args, **kwargs):
#         if not self.pk:  # If the user is being created (not updated)
#             if self.is_teacher:
#                 self.verification_status = False #Teachers need manual validation
#             else:
#                 self.verification_status = True #Students login immediately
#
#                 # Hash the password before saving
#             self.password = make_password(self.password)
#         super().save(*args, **kwargs)
#
#     def check_password(self, raw_password):
#         """Compare a raw password with the hashed password."""
#         return check_password(raw_password, self.password)
#
#     def __str__(self):
#         return self.username

class User(AbstractUser):  # Extending Django's default user model
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    is_teacher = models.BooleanField(default=False)
    verification_status = models.BooleanField(default=False)  # Controlled by frontend

    def __str__(self):
        return self.username


# class Lesson(models.Model):
#     teacher = models.ForeignKey(User, on_delete=models.CASCADE)
#     name = models.CharField(max_length=100)
#     lesson_type = models.CharField(max_length=100)
#     jlpt_level = models.IntegerField()
#     exercise_count = models.IntegerField()
#
#     def __str__(self):
#         return self.name


class Lesson(models.Model):
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    lesson_type = models.CharField(max_length=100, default='mixed')
    jlpt_level = models.CharField(max_length=10, default='1-5')  # Changed to CharField to handle ranges
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


class ExerciseMatch(models.Model):
    jlpt_level = models.IntegerField()

    def __str__(self):
        return f"Match Exercise Level {self.jlpt_level}"

class FreetextSubmission(models.Model):
    exercise = models.ForeignKey(ExerciseFreetext, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    student_answer = models.TextField()
    submission_date = models.DateTimeField(auto_now_add=True)
    is_reviewed = models.BooleanField(default=False)
    is_correct = models.BooleanField(default=False)
    teacher_feedback = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Submission by {self.student.username} for {self.exercise.question[:30]}"


class ExerciseMatchOptions(models.Model):
    exercise_match = models.ForeignKey(ExerciseMatch, on_delete=models.CASCADE)
    kanji = models.TextField()
    answer = models.TextField()

    def __str__(self):
        return f"{self.kanji} - {self.answer}"


# class LessonsExercises(models.Model):
#     lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
#     exercise_id = models.IntegerField()  # Exercise ID can be from any of the exercise tables
#     exercise_type = models.CharField(max_length=50)  # This can be a string indicating the type of exercise
#
#     def save(self, *args, **kwargs):
#         super().save(*args, **kwargs)
#         self.update_lesson_type()
#
#     def delete(self, *args, **kwargs):
#         super().delete(*args, **kwargs)
#         self.update_lesson_type()
#
#     def update_lesson_type(self):
#         lesson_exercises = LessonsExercises.objects.filter(lesson=self.lesson)
#         exercise_types = set(lesson_exercises.values_list('exercise_type', flat=True))
#
#         if len(exercise_types) == 1:
#             self.lesson.lesson_type = exercise_types.pop()
#         else:
#             self.lesson.lesson_type = 'mixed'
#         self.lesson.save()
#
#     def __str__(self):
#         return f"{self.lesson.name} - {self.exercise_id} ({self.exercise_type})"

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
