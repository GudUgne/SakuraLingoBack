from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User, ExerciseMatch, ExerciseMatchOptions, Group,\
    GroupsStudents, Chat, ExerciseMultiChoice, ExerciseMultiChoiceOptions, ExerciseFreetext, \
     Lesson, LessonsExercises

# AUTHORISATION - USER SERIALIZERS
class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

class UserUpdateSerializer(serializers.ModelSerializer):
    current_password = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'username', 'email',
            'current_password', 'password',
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name':  {'required': False},
            'username':   {'required': False},
            'email':      {'required': False},
        }

    def validate(self, attrs):
        new_pw = attrs.get('password')
        if new_pw is not None:
            curr = attrs.get('current_password')
            if not curr:
                raise serializers.ValidationError({
                    'current_password': 'You must provide your current password to set a new one.'
                })
            if not self.instance.check_password(curr):
                raise serializers.ValidationError({
                    'current_password': 'Current password is incorrect.'
                })
        return attrs

    def update(self, instance, validated_data):
        new_pw = validated_data.pop('password', None)
        validated_data.pop('current_password', None)

        instance = super().update(instance, validated_data)

        if new_pw:
            instance.set_password(new_pw)
            instance.save()

        return instance


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'username', 'email', 'password', 'is_teacher', 'verification_status']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        is_teacher = validated_data.get("is_teacher", False)
        validated_data.pop("verification_status", None)

        user = User.objects.create_user(**validated_data)
        user.verification_status = not is_teacher
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Invalid username or password.")
        return {"user": user}


# EXERCISE SERIALIZERS
class ExerciseFreetextSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseFreetext
        fields = ['id', 'question', 'answer', 'jlpt_level']

class ExerciseMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseMatch
        fields = ['id', 'jlpt_level']

class ExerciseMatchOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseMatchOptions
        fields = ['id', 'exercise_match', 'kanji', 'answer']

class ExerciseMultiChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseMultiChoice
        fields = ['id', 'question', 'jlpt_level']

class ExerciseMultiChoiceOptionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseMultiChoiceOptions
        fields = ['id', 'exercise_mc', 'answer', 'is_correct']


# GROUP SERIALIZERS
class GroupSerializer(serializers.ModelSerializer):
    teacher = UserSimpleSerializer(read_only=True)

    class Meta:
        model = Group
        fields = ['id', 'name', 'teacher']

class GroupsStudentsSerializer(serializers.ModelSerializer):
    student = UserSimpleSerializer(read_only=True)
    group = GroupSerializer(read_only=True)

    class Meta:
        model = GroupsStudents
        fields = ['id', 'student', 'group', 'verification_status']


# CHAT SERIALIZERS
class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = '__all__'


# LESSON SERIALIZERS
class LessonSerializer(serializers.ModelSerializer):
    teacher = UserSimpleSerializer(read_only=True)

    class Meta:
        model = Lesson
        fields = ['id', 'name', 'lesson_type', 'jlpt_level', 'exercise_count', 'teacher']
        read_only_fields = ['lesson_type', 'exercise_count']  # These are auto-calculated


class LessonsExercisesSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonsExercises
        fields = ['id', 'lesson', 'exercise_id', 'exercise_type']


class LessonDetailSerializer(serializers.ModelSerializer):
    """Detailed lesson serializer with exercises included"""
    teacher = UserSimpleSerializer(read_only=True)
    exercises = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ['id', 'name', 'lesson_type', 'jlpt_level', 'exercise_count', 'teacher', 'exercises']

    def get_exercises(self, obj):
        lesson_exercises = LessonsExercises.objects.filter(lesson=obj)
        exercises = []

        for le in lesson_exercises:
            exercise_data = {
                'id': le.exercise_id,
                'type': le.exercise_type,
                'lesson_exercise_id': le.id
            }

            # Fetch actual exercise data based on type
            try:
                if le.exercise_type == 'freetext':
                    exercise = ExerciseFreetext.objects.get(id=le.exercise_id)
                    exercise_data.update({
                        'question': exercise.question,
                        'answer': exercise.answer,
                        'jlpt_level': exercise.jlpt_level
                    })
                elif le.exercise_type == 'multi-choice':
                    exercise = ExerciseMultiChoice.objects.get(id=le.exercise_id)
                    options = ExerciseMultiChoiceOptions.objects.filter(exercise_mc=exercise)
                    exercise_data.update({
                        'question': exercise.question,
                        'jlpt_level': exercise.jlpt_level,
                        'options': ExerciseMultiChoiceOptionsSerializer(options, many=True).data
                    })
                elif le.exercise_type == 'pair-match':
                    exercise = ExerciseMatch.objects.get(id=le.exercise_id)
                    # Get ALL pairs for this exercise, not just the first one
                    pairs = ExerciseMatchOptions.objects.filter(exercise_match=exercise)
                    exercise_data.update({
                        'jlpt_level': exercise.jlpt_level,
                        'pairs': [{'kanji': pair.kanji, 'answer': pair.answer} for pair in pairs],  # ✅ All pairs
                        'pair_count': pairs.count()
                    })
            except Exception as e:
                # Exercise might be deleted, skip it
                continue

            exercises.append(exercise_data)

        return exercises


class LessonCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating lessons with exercises"""
    exercises = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField()
        ),
        write_only=True,
        required=False
    )

    class Meta:
        model = Lesson
        fields = ['id', 'name', 'lesson_type', 'jlpt_level', 'exercise_count', 'exercises']
        read_only_fields = ['lesson_type', 'exercise_count']

    def create(self, validated_data):
        exercises_data = validated_data.pop('exercises', [])

        # Create the lesson
        lesson = Lesson.objects.create(**validated_data)

        # Add exercises to the lesson
        for exercise_data in exercises_data:
            LessonsExercises.objects.create(
                lesson=lesson,
                exercise_id=exercise_data['id'],
                exercise_type=exercise_data['type']
            )

        # Update lesson stats (this will be done automatically by the model's save method)
        lesson.exercise_count = len(exercises_data)
        lesson.save()

        return lesson