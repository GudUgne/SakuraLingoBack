from django.shortcuts import render, get_object_or_404
from django.contrib.auth import login
from django.utils import timezone
from django.db.models import Q

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status, viewsets, generics, permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ExerciseMatch, Group, GroupsStudents, User, Chat
from .serializers import UserUpdateSerializer, UserSimpleSerializer, LoginSerializer, RegisterSerializer, ExerciseMatchSerializer, GroupSerializer, GroupsStudentsSerializer, ChatSerializer


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
        # Return the updated fields
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

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                "message": "User registered successfully!",
                "verification_status": user.verification_status,
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            }, status=status.HTTP_201_CREATED)

        print("Registration error:", serializer.errors)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)  # Django logs in the user

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                "message": "Login successful!",
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class ExerciseMatchViewSet(viewsets.ModelViewSet):
#     queryset = ExerciseMatch.objects.all()
#     serializer_class = ExerciseMatchSerializer

class ExerciseMatchListCreateView(APIView):
    def get(self, request):
        matches = ExerciseMatch.objects.all()
        serializer = ExerciseMatchSerializer(matches, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ExerciseMatchSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
        )
        serializer = GroupsStudentsSerializer(requests, many=True)
        return Response(serializer.data)


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

        # (keep your existing permission checks here…)

        # fetch ALL join‐records, regardless of status
        rels = GroupsStudents.objects.filter(group=group).select_related('student')

        students = []
        for rel in rels:
            students.append({
                "id":                 rel.student.id,
                "first_name":         rel.student.first_name,
                "last_name":          rel.student.last_name,
                "verification_status": rel.verification_status,  # include the flag
            })

        return Response({
            "id":       group.id,
            "name":     group.name,
            "students": students
        })


class ExerciseMatchOptionsListCreateView(APIView):
    def get(self, request):
        options = ExerciseMatchOptions.objects.all()
        serializer = ExerciseMatchOptionSerializer(options, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ExerciseMatchOptionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)