from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    LoginView,
    ExerciseMatchListCreateView,
    MyGroupsView,
    CreateGroupView,
    RequestToJoinGroup,
    PendingRequestsView,
    ApproveRequestView, CurrentUserView, MyPendingRequestsView,
SendMessageView, GetConversationView, UserListView, SearchGroupsView, CancelRequestView, GroupDetailView,
)

router = DefaultRouter()
# router.register(r'exercise-match', ExerciseMatchViewSet, basename='exercise-match')

urlpatterns = [
    path('', include(router.urls)),
    path('users/register/', RegisterView.as_view(), name='register'),
    path('users/login/', LoginView.as_view(), name='login'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/me/', CurrentUserView.as_view(), name='current-user'),

    path('exercise-match/', ExerciseMatchListCreateView.as_view(), name='exercise-match'),

    path('groups/', MyGroupsView.as_view(), name='my-groups'),
    path('groups/search/', SearchGroupsView.as_view(), name='search-groups'),
    path('groups/create/', CreateGroupView.as_view(), name='create-group'),
    path('groups/<int:group_id>/request/', RequestToJoinGroup.as_view(), name='request-join'),
    path('groups/requests/', PendingRequestsView.as_view(), name='pending-requests'),
    path('groups/my-pending-requests/', MyPendingRequestsView.as_view(), name='my-pending-requests'),
    path('groups/<int:group_id>/approve/<int:student_id>/', ApproveRequestView.as_view(), name='approve-student'),
path(
  'groups/<int:group_id>/',
  GroupDetailView.as_view(),
  name='group-detail'
),
path(
  'groups/<int:group_id>/requests/<int:request_id>/',
  CancelRequestView.as_view(),
  name='cancel-request'
),

    path('messages/send/',SendMessageView.as_view(), name='send_message'),
    path('messages/conversation/', GetConversationView.as_view(), name='get_conversation'),
]
