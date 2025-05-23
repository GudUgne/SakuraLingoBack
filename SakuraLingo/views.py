from django.shortcuts import render, get_object_or_404
from django.contrib.auth import login
from django.utils import timezone
from django.db.models import Q, Count

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, viewsets, generics, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    ExerciseMatch, Group, GroupsStudents, User, Chat, ExerciseMatchOptions,
    ExerciseMultiChoiceOptions, ExerciseMultiChoice, ExerciseFreetext,
    Lesson, LessonsExercises
)

from .serializers import UserUpdateSerializer, UserSimpleSerializer, LoginSerializer, RegisterSerializer, \
    ExerciseMatchSerializer, GroupSerializer, GroupsStudentsSerializer, ChatSerializer, ExerciseMatchOptionsSerializer, \
    ExerciseMultiChoiceSerializer, ExerciseMultiChoiceOptionsSerializer, \
    ExerciseFreetextSerializer, FreetextSubmissionSerializer, \
    LessonDetailSerializer, LessonCreateSerializer, LessonsExercisesSerializer, LessonSerializer

# USER - AUTHORISATION VIEWS
class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = RegisterSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserUpdateSerializer(user).data, status=status.HTTP_200_OK)

class UserListView(APIView):
    def get(self, request):
        users = User.objects.all()
        serializer = UserSimpleSerializer(users, many=True)
        return Response(serializer.data)

class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "User registered successfully!",
                "verification_status": user.verification_status,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            refresh = RefreshToken.for_user(user)
            return Response({
                "message": "Login successful!",
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# EXERCISE VIEWS
class ExerciseMatchListCreateView(APIView):
    def get(self, request):
        """Get all matching exercises with their pairs - only real exercises with 2+ pairs"""
        matches = ExerciseMatch.objects.all()
        result = []

        for match in matches:
            # Get all pairs for this exercise
            pairs = ExerciseMatchOptions.objects.filter(exercise_match=match)
            pair_count = pairs.count()

            # Only include exercises with 2 or more pairs (real exercises, not single library pairs)
            if pair_count >= 2:
                match_data = {
                    'id': match.id,
                    'jlpt_level': match.jlpt_level,
                    'pairs': [{'kanji': pair.kanji, 'answer': pair.answer} for pair in pairs],
                    'pair_count': pair_count
                }
                result.append(match_data)

        return Response(result)

    def post(self, request):
        """Create a new matching exercise with multiple pairs"""
        jlpt_level = request.data.get('jlpt_level')
        pairs_data = request.data.get('pairs', [])

        if not pairs_data or len(pairs_data) < 2:
            return Response(
                {'detail': 'At least 2 pairs are required for a matching exercise'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the exercise
        exercise_match = ExerciseMatch.objects.create(jlpt_level=jlpt_level)

        # Create all the pairs for this exercise
        for pair_data in pairs_data:
            kanji = pair_data.get('kanji', '')
            answer = pair_data.get('answer', '')

            if not kanji or not answer:
                exercise_match.delete()
                return Response(
                    {'detail': 'Each pair must have both kanji and answer'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            ExerciseMatchOptions.objects.create(
                exercise_match=exercise_match,
                kanji=kanji,
                answer=answer
            )

        # Return the created exercise with its pairs
        pairs = ExerciseMatchOptions.objects.filter(exercise_match=exercise_match)
        return Response({
            'id': exercise_match.id,
            'jlpt_level': exercise_match.jlpt_level,
            'pairs': [{'kanji': pair.kanji, 'answer': pair.answer} for pair in pairs],
            'pair_count': pairs.count()
        }, status=status.HTTP_201_CREATED)

    def delete(self, request, match_id):
        """Delete a matching exercise and all its pairs"""
        try:
            match = ExerciseMatch.objects.get(id=match_id)
            ExerciseMatchOptions.objects.filter(exercise_match=match).delete()
            match.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ExerciseMatch.DoesNotExist:
            return Response({'detail': 'Exercise not found'}, status=status.HTTP_404_NOT_FOUND)


# 1. GET /api/groups/ → User's groups (joined or owned)
class MyGroupsView(generics.ListAPIView):
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_teacher:
            return Group.objects.filter(teacher=user)
        else:
            student_groups = GroupsStudents.objects.filter(
                student=user, verification_status=True
            )
            return Group.objects.filter(id__in=student_groups.values_list('group_id', flat=True))


# 2. POST /api/groups/create/ → Create a group (teachers only)
class CreateGroupView(generics.CreateAPIView):
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_teacher:
            raise PermissionDenied("Only teachers can create groups.")
        serializer.save(teacher=user)


# 3. POST /api/groups/<group_id>/request/ → Request to join a group (students only)
class RequestToJoinGroup(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id):
        user = request.user
        if user.is_teacher:
            return Response({"detail": "Teachers can't join groups."}, status=400)

        group = get_object_or_404(Group, id=group_id)

        already_exists = GroupsStudents.objects.filter(group=group, student=user).exists()
        if already_exists:
            return Response({"detail": "Already requested or joined."}, status=400)

        GroupsStudents.objects.create(group=group, student=user)
        return Response({"detail": "Request sent!"}, status=201)

    def delete(self, request, group_id):
        user = request.user
        group = get_object_or_404(Group, id=group_id)

        try:
            request_obj = GroupsStudents.objects.get(group=group, student=user)
            request_obj.delete()
            return Response({"detail": "Request withdrawn successfully."}, status=200)
        except GroupsStudents.DoesNotExist:
            return Response({"detail": "No request found to withdraw."}, status=404)


# 4. GET /api/groups/requests/ → Get pending student join requests (teachers only)
class PendingRequestsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.is_teacher:
            return Response(status=403)

        teacher_groups = Group.objects.filter(teacher=request.user)
        requests = GroupsStudents.objects.filter(
            group__in=teacher_groups, verification_status=False
        ).select_related('student', 'group')

        # Custom serialization to include proper student names
        requests_data = []
        for req in requests:
            requests_data.append({
                'id': req.id,
                'student': {
                    'id': req.student.id,
                    'username': req.student.username,
                    'first_name': req.student.first_name,
                    'last_name': req.student.last_name,
                },
                'group': {
                    'id': req.group.id,
                    'name': req.group.name,
                },
                'verification_status': req.verification_status
            })

        return Response(requests_data)

# 5. POST /api/groups/<group_id>/approve/<student_id>/ → Approve student (teachers only)
class ApproveRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, group_id, student_id):
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can approve students."}, status=403)

        group = get_object_or_404(Group, id=group_id, teacher=request.user)

        try:
            relation = GroupsStudents.objects.get(group=group, student__id=student_id)
            relation.verification_status = True
            relation.save()
            return Response({"detail": "Student approved!"})
        except GroupsStudents.DoesNotExist:
            return Response({"detail": "Request not found."}, status=404)

# for teacher to cancel students class request
class CancelRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, group_id, request_id):
        # only the teacher of that group may cancel
        group = get_object_or_404(Group, id=group_id, teacher=request.user)

        # only delete a still‐pending join‐request
        join_req = get_object_or_404(
            GroupsStudents,
            id=request_id,
            group=group,
            verification_status=False
        )
        join_req.delete()
        return Response({"detail": "Request cancelled"}, status=status.HTTP_204_NO_CONTENT)

class SearchGroupsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        name_query = request.query_params.get('name', '')
        if not name_query:
            return Response([])

        groups = Group.objects.filter(name__icontains=name_query)
        serializer = GroupSerializer(groups, many=True)
        return Response(serializer.data)


class MyPendingRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pending = GroupsStudents.objects.filter(
            student=request.user,
            verification_status=False
        )
        serializer = GroupsStudentsSerializer(pending, many=True)
        return Response(serializer.data)


class SendMessageView(APIView):
    def post(self, request):
        sender_id = request.data.get('sender_id')
        receiver_id = request.data.get('receiver_id')
        message_content = request.data.get('message_content')
        is_group = request.data.get('is_group_message', False)

        if not all([sender_id, receiver_id, message_content]):
            return Response({'error': 'Missing fields'}, status=400)

        # chat = Chat.objects.create(
        #     sender_id=sender_id,
        #     receiver_id=receiver_id,
        #     message_content=message_content,
        #     time_sent=timezone.now(),
        #     is_group_message=False  # Only 1-on-1 chat for now
        # )
        kwargs = dict(
            sender_id=sender_id,
            message_content=message_content,
            time_sent=timezone.now(),
            is_group_message=is_group,
        )
        if is_group:
            kwargs['group_id'] = receiver_id
        else:
            kwargs['receiver_id'] = receiver_id

        chat = Chat.objects.create(**kwargs)

        serializer = ChatSerializer(chat)
        return Response(serializer.data, status=201)  # 201 Created


class GetConversationView(APIView):
    def get(self, request):
        user1 = request.GET.get('user1')
        user2 = request.GET.get('user2')
        group_id = request.GET.get('group_id')

        # if not all([user1, user2]):
        #     return Response({'error': 'Missing user ids'}, status=400)
        #
        # messages = Chat.objects.filter(
        #     (Q(sender_id=user1, receiver_id=user2)) |
        #     (Q(sender_id=user2, receiver_id=user1))
        # ).order_by('time_sent')

        # fetch all messages in a group
        if group_id:
            messages = Chat.objects.filter(
                is_group_message=True,
                group_id=group_id
            ).order_by('time_sent')
            serializer = ChatSerializer(messages, many=True)
            return Response(serializer.data)

        if user1 and user2:
            # Fetch conversation between two specific users
            messages = Chat.objects.filter(
                (Q(sender_id=user1, receiver_id=user2)) |
                (Q(sender_id=user2, receiver_id=user1))
            ).order_by('time_sent')
        elif user1:
            # Fetch all messages involving this user
            messages = Chat.objects.filter(
                Q(sender_id=user1) | Q(receiver_id=user1)
            ).order_by('-time_sent')
        else:
            return Response({'error': 'Missing user id(s)'}, status=400)

        serializer = ChatSerializer(messages, many=True)
        return Response(serializer.data)

#     view to see extended class information
class GroupDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, group_id):
        group = get_object_or_404(Group, id=group_id)

        # Check if user has access to this group
        user = request.user
        has_access = False

        if user.is_teacher and group.teacher == user:
            has_access = True
        elif not user.is_teacher:
            # Student can access if they're a member (approved or pending)
            has_access = GroupsStudents.objects.filter(
                group=group,
                student=user
            ).exists()

        if not has_access:
            return Response(
                {"detail": "You don't have permission to access this group"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Fetch ALL join records, regardless of status
        rels = GroupsStudents.objects.filter(group=group).select_related('student')

        students = []
        for rel in rels:
            students.append({
                "id": rel.student.id,
                "first_name": rel.student.first_name,
                "last_name": rel.student.last_name,
                "username": rel.student.username,
                "verification_status": rel.verification_status,
            })

        return Response({
            "id": group.id,
            "name": group.name,
            "students": students
        })



class ExerciseMultiChoiceView(APIView):
    def get(self, request):
        """Get all multiple choice questions with their options."""
        try:
            questions = ExerciseMultiChoice.objects.all()
            result = []

            for question in questions:
                question_data = ExerciseMultiChoiceSerializer(question).data
                options = ExerciseMultiChoiceOptions.objects.filter(exercise_mc=question)
                question_data['options'] = ExerciseMultiChoiceOptionsSerializer(options, many=True).data
                result.append(question_data)

            return Response(result)
        except Exception as e:
            print(f"Error in GET: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Create a new multiple choice question with options."""
        try:
            print("Received POST request with data:", request.data)

            question_data = {
                'question': request.data.get('question'),
                'jlpt_level': request.data.get('jlpt_level')
            }

            print("Question data:", question_data)

            # Validate and save the question
            question_serializer = ExerciseMultiChoiceSerializer(data=question_data)
            if not question_serializer.is_valid():
                print("Question serializer errors:", question_serializer.errors)
                return Response(question_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Check that options were provided
            options_data = request.data.get('options', [])
            print("Options data:", options_data)

            if not options_data:
                return Response(
                    {'detail': 'At least one option is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Ensure at least one option is marked as correct
            correct_options = [opt for opt in options_data if opt.get('is_correct')]
            if not correct_options:
                return Response(
                    {'detail': 'At least one option must be marked as correct'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Save the question
            question = question_serializer.save()
            print("Question saved with ID:", question.id)

            # Save each option
            for i, option_data in enumerate(options_data):
                print(f"Processing option {i + 1}:", option_data)

                option = {
                    'exercise_mc': question.id,
                    'answer': option_data.get('answer'),
                    'is_correct': option_data.get('is_correct', False)
                }

                print(f"Formatted option {i + 1}:", option)

                option_serializer = ExerciseMultiChoiceOptionsSerializer(data=option)
                if option_serializer.is_valid():
                    option_serializer.save()
                    print(f"Option {i + 1} saved successfully")
                else:
                    print(f"Option {i + 1} validation errors:", option_serializer.errors)
                    # Delete the question if option validation fails
                    question.delete()
                    return Response(
                        option_serializer.errors,
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Return the complete question with options
            result = self.get_question_with_options(question)
            print("Returning result:", result)
            return Response(result, status=status.HTTP_201_CREATED)

        except Exception as e:
            import traceback
            print(f"Error in POST: {str(e)}")
            print(traceback.format_exc())
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, question_id):
        """Delete a multiple choice question and all its options."""
        try:
            question = ExerciseMultiChoice.objects.get(id=question_id)

            # Delete all options first
            ExerciseMultiChoiceOptions.objects.filter(exercise_mc=question).delete()
            # Delete the question
            question.delete()

            return Response(status=status.HTTP_204_NO_CONTENT)
        except ExerciseMultiChoice.DoesNotExist:
            return Response({'detail': 'Question not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error in DELETE: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_question_with_options(self, question):
        """Helper to format a question with its options."""
        question_data = ExerciseMultiChoiceSerializer(question).data
        options = ExerciseMultiChoiceOptions.objects.filter(exercise_mc=question)
        question_data['options'] = ExerciseMultiChoiceOptionsSerializer(options, many=True).data
        return question_data


class ExerciseFreetextListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        exercises = ExerciseFreetext.objects.all()
        serializer = ExerciseFreetextSerializer(exercises, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Only teachers can create exercises
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can create exercises"},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = ExerciseFreetextSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExerciseFreetextViewSet(viewsets.ModelViewSet):
    queryset = ExerciseFreetext.objects.all()
    serializer_class = ExerciseFreetextSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Teachers can see all exercises, students only see published ones
        if self.request.user.is_teacher:
            return ExerciseFreetext.objects.all()
        return ExerciseFreetext.objects.filter(is_published=True)

class FreetextSubmissionViewSet(viewsets.ModelViewSet):
    serializer_class = FreetextSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_teacher:
            # Teachers can see all submissions
            return FreetextSubmission.objects.all()
        # Students can only see their own submissions
        return FreetextSubmission.objects.filter(student=user)

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)


class TeacherReviewSubmissionView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, submission_id):
        # Ensure user is a teacher
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can review submissions"}, status=status.HTTP_403_FORBIDDEN)

        submission = get_object_or_404(FreetextSubmission, id=submission_id)
        serializer = FreetextSubmissionSerializer(submission, data=request.data, partial=True)
        if serializer.is_valid():
            submission = serializer.save(is_reviewed=True)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PendingSubmissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Ensure user is a teacher
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can view pending submissions"}, status=status.HTTP_403_FORBIDDEN)

        pending = FreetextSubmission.objects.filter(is_reviewed=False)
        serializer = FreetextSubmissionSerializer(pending, many=True)
        return Response(serializer.data)


class PendingFreetextSubmissionsView(generics.ListAPIView):
    serializer_class = FreetextSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if not self.request.user.is_teacher:
            return FreetextSubmission.objects.none()
        return FreetextSubmission.objects.filter(is_reviewed=False)


class ExerciseFreetextDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return ExerciseFreetext.objects.get(pk=pk)
        except ExerciseFreetext.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        exercise = self.get_object(pk)
        serializer = ExerciseFreetextSerializer(exercise)
        return Response(serializer.data)

    def put(self, request, pk):
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can update exercises"},
                            status=status.HTTP_403_FORBIDDEN)

        exercise = self.get_object(pk)
        serializer = ExerciseFreetextSerializer(exercise, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can delete exercises"},
                            status=status.HTTP_403_FORBIDDEN)

        exercise = self.get_object(pk)
        exercise.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# LESSON VIEWS
class LessonListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return LessonCreateSerializer
        return LessonSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_teacher:
            # Teachers see all lessons (or just their own - adjust as needed)
            return Lesson.objects.all().select_related('teacher')
        else:
            # Students see all lessons
            return Lesson.objects.all().select_related('teacher')

    def perform_create(self, serializer):
        if not self.request.user.is_teacher:
            raise PermissionDenied("Only teachers can create lessons.")
        serializer.save(teacher=self.request.user)


class LessonDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = LessonDetailSerializer

    def get_queryset(self):
        return Lesson.objects.all().select_related('teacher')

    def perform_update(self, serializer):
        if not self.request.user.is_teacher:
            raise PermissionDenied("Only teachers can update lessons.")

        lesson = self.get_object()
        if lesson.teacher != self.request.user:
            raise PermissionDenied("You can only update your own lessons.")

        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_teacher:
            raise PermissionDenied("Only teachers can delete lessons.")

        if instance.teacher != self.request.user:
            raise PermissionDenied("You can only delete your own lessons.")

        instance.delete()


class LessonExercisesView(APIView):
    """Manage exercises within a lesson"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, lesson_id):
        """Get all exercises for a lesson"""
        lesson = get_object_or_404(Lesson, id=lesson_id)
        lesson_exercises = LessonsExercises.objects.filter(lesson=lesson)
        serializer = LessonsExercisesSerializer(lesson_exercises, many=True)
        return Response(serializer.data)

    def post(self, request, lesson_id):
        """Add exercises to a lesson"""
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can add exercises to lessons."},
                            status=status.HTTP_403_FORBIDDEN)

        lesson = get_object_or_404(Lesson, id=lesson_id)

        if lesson.teacher != request.user:
            return Response({"detail": "You can only modify your own lessons."},
                            status=status.HTTP_403_FORBIDDEN)

        exercises_data = request.data
        if not isinstance(exercises_data, list):
            return Response({"detail": "Expected a list of exercises."},
                            status=status.HTTP_400_BAD_REQUEST)

        created_exercises = []
        for exercise_data in exercises_data:
            lesson_exercise = LessonsExercises.objects.create(
                lesson=lesson,
                exercise_id=exercise_data['exercise_id'],
                exercise_type=exercise_data['exercise_type']
            )
            created_exercises.append(lesson_exercise)

        # Update lesson exercise count
        lesson.exercise_count = LessonsExercises.objects.filter(lesson=lesson).count()
        lesson.save()

        serializer = LessonsExercisesSerializer(created_exercises, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, lesson_id, exercise_id=None):
        """Remove an exercise from a lesson"""
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can remove exercises from lessons."},
                            status=status.HTTP_403_FORBIDDEN)

        lesson = get_object_or_404(Lesson, id=lesson_id)

        if lesson.teacher != request.user:
            return Response({"detail": "You can only modify your own lessons."},
                            status=status.HTTP_403_FORBIDDEN)

        if exercise_id:
            lesson_exercise = get_object_or_404(LessonsExercises,
                                                lesson=lesson,
                                                id=exercise_id)
            lesson_exercise.delete()

        # Update lesson exercise count
        lesson.exercise_count = LessonsExercises.objects.filter(lesson=lesson).count()
        lesson.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class AllExercisesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Fetch all exercise types
        freetext_exercises = ExerciseFreetext.objects.all()
        multichoice_exercises = ExerciseMultiChoice.objects.all()

        # Only get match exercises with 2+ pairs (real exercises, not library pairs)
        match_exercises = ExerciseMatch.objects.annotate(
            pair_count=Count('exercisematchoptions')
        ).filter(pair_count__gte=2)

        # Format freetext exercises
        freetext_data = []
        for exercise in freetext_exercises:
            freetext_data.append({
                'id': exercise.id,
                'type': 'freetext',
                'question': exercise.question,
                'answer': exercise.answer,
                'jlpt_level': exercise.jlpt_level
            })

        # Format multi-choice exercises
        multichoice_data = []
        for exercise in multichoice_exercises:
            options = ExerciseMultiChoiceOptions.objects.filter(exercise_mc=exercise)
            multichoice_data.append({
                'id': exercise.id,
                'type': 'multi-choice',
                'question': exercise.question,
                'jlpt_level': exercise.jlpt_level,
                'options': ExerciseMultiChoiceOptionsSerializer(options, many=True).data
            })

        # Format pair-match exercises
        match_data = []
        for exercise in match_exercises:
            pairs = ExerciseMatchOptions.objects.filter(exercise_match=exercise)
            # Get first pair for display purposes, but include all pairs
            first_pair = pairs.first()
            match_data.append({
                'id': exercise.id,
                'type': 'pair-match',
                'jlpt_level': exercise.jlpt_level,
                'kanji': first_pair.kanji if first_pair else '',
                'answer': first_pair.answer if first_pair else '',
                'pairs': [{'kanji': pair.kanji, 'answer': pair.answer} for pair in pairs],
                'pair_count': pairs.count()
            })

        return Response({
            'freetext': freetext_data,
            'multiChoice': multichoice_data,
            'pairMatch': match_data
        })


class PairLibraryView(APIView):
    """Manage individual pairs that can be reused in exercises"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get all available pairs - separate library pairs from exercise pairs"""
        jlpt_level = request.query_params.get('jlpt_level')

        # Get exercises that have only 1 pair (these are library pairs)
        library_exercises = ExerciseMatch.objects.annotate(
            pair_count=Count('exercisematchoptions')
        ).filter(pair_count=1)

        pairs_query = ExerciseMatchOptions.objects.filter(exercise_match__in=library_exercises)

        if jlpt_level and jlpt_level != 'all':
            pairs_query = pairs_query.filter(exercise_match__jlpt_level=jlpt_level)

        pairs = pairs_query.select_related('exercise_match')

        pair_data = []
        for pair in pairs:
            pair_data.append({
                'id': pair.id,
                'kanji': pair.kanji,
                'answer': pair.answer,
                'jlpt_level': pair.exercise_match.jlpt_level,
                'exercise_id': pair.exercise_match.id,
                'can_reuse': True
            })

        return Response(pair_data)

    def post(self, request):
        """Create individual pairs for the library"""
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can create pairs"},
                            status=status.HTTP_403_FORBIDDEN)

        kanji = request.data.get('kanji')
        answer = request.data.get('answer')
        jlpt_level = request.data.get('jlpt_level', 5)

        if not kanji or not answer:
            return Response({"detail": "Kanji and answer are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Check for exact duplicates in library pairs only
        library_exercises = ExerciseMatch.objects.annotate(
            pair_count=Count('exercisematchoptions')
        ).filter(pair_count=1)

        if ExerciseMatchOptions.objects.filter(
                exercise_match__in=library_exercises,
                kanji__iexact=kanji,
                answer__iexact=answer
        ).exists():
            return Response({"detail": "This pair already exists in the library"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Create a single-pair exercise to hold this library pair
        temp_exercise = ExerciseMatch.objects.create(jlpt_level=jlpt_level)

        pair = ExerciseMatchOptions.objects.create(
            exercise_match=temp_exercise,
            kanji=kanji,
            answer=answer
        )

        return Response({
            'id': pair.id,
            'kanji': pair.kanji,
            'answer': pair.answer,
            'jlpt_level': jlpt_level,
            'exercise_id': temp_exercise.id,
            'can_reuse': True
        }, status=status.HTTP_201_CREATED)


class CreateExerciseFromPairsView(APIView):
    """Create an exercise by selecting existing pairs"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can create exercises"},
                            status=status.HTTP_403_FORBIDDEN)

        pair_ids = request.data.get('pair_ids', [])
        jlpt_level = request.data.get('jlpt_level')

        if len(pair_ids) < 2:
            return Response({"detail": "At least 2 pairs are required"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Get the selected pairs
        selected_pairs = ExerciseMatchOptions.objects.filter(id__in=pair_ids)

        if selected_pairs.count() != len(pair_ids):
            return Response({"detail": "Some pairs not found"},
                            status=status.HTTP_400_BAD_REQUEST)

        # Create new exercise
        new_exercise = ExerciseMatch.objects.create(jlpt_level=jlpt_level)

        # COPY (don't move) selected pairs to the new exercise
        # This ensures library pairs remain available for reuse
        for pair in selected_pairs:
            ExerciseMatchOptions.objects.create(
                exercise_match=new_exercise,
                kanji=pair.kanji,
                answer=pair.answer
            )

        # Return the new exercise
        new_pairs = ExerciseMatchOptions.objects.filter(exercise_match=new_exercise)
        return Response({
            'id': new_exercise.id,
            'jlpt_level': new_exercise.jlpt_level,
            'pairs': [{'kanji': p.kanji, 'answer': p.answer} for p in new_pairs],
            'pair_count': new_pairs.count()
        }, status=status.HTTP_201_CREATED)


class RemoveStudentFromGroupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, group_id, student_id):
        """Remove a student from a group (teachers only)"""
        if not request.user.is_teacher:
            return Response({"detail": "Only teachers can remove students from groups"},
                            status=status.HTTP_403_FORBIDDEN)

        # Get the group and verify the teacher owns it
        group = get_object_or_404(Group, id=group_id, teacher=request.user)

        # Find and remove the student from the group
        try:
            group_student = GroupsStudents.objects.get(group=group, student_id=student_id)
            group_student.delete()
            return Response({"detail": "Student removed from group successfully"},
                            status=status.HTTP_200_OK)
        except GroupsStudents.DoesNotExist:
            return Response({"detail": "Student not found in this group"},
                            status=status.HTTP_404_NOT_FOUND)
