from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *
router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('users/register/', RegisterView.as_view(), name='register'),
    path('users/login/', LoginView.as_view(), name='login'),
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/me/', CurrentUserView.as_view(), name='current-user'),

    path('exercise-match/', ExerciseMatchListCreateView.as_view(), name='exercise-match-list'),
    path('exercise-match/<int:match_id>/', ExerciseMatchListCreateView.as_view(), name='exercise-match-detail'),

    path('pair-library/', PairLibraryView.as_view(), name='pair-library'),
    path('create-exercise-from-pairs/', CreateExerciseFromPairsView.as_view(), name='create-exercise-from-pairs'),

    path('exercise-multichoice/', ExerciseMultiChoiceView.as_view(), name='exercise-multichoice-list'),
    path('exercise-multichoice/<int:question_id>/', ExerciseMultiChoiceView.as_view(),
         name='exercise-multichoice-detail'),

    path('exercise-freetext/', ExerciseFreetextListCreateView.as_view(), name='exercise-freetext-list'),
    path('exercise-freetext/<int:pk>/', ExerciseFreetextDetailView.as_view(), name='exercise-freetext-detail'),

    path('exercises/all/', AllExercisesView.as_view(), name='all-exercises'),

    path('lessons/', LessonListCreateView.as_view(), name='lesson-list-create'),
    path('lessons/<int:pk>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('lessons/<int:lesson_id>/exercises/', LessonExercisesView.as_view(), name='lesson-exercises'),
    path('lessons/<int:lesson_id>/exercises/<int:exercise_id>/', LessonExercisesView.as_view(),
         name='lesson-exercise-detail'),


    path('homework/assign/', HomeworkAssignView.as_view(), name='homework-assign'),
    path('homework/teacher/', TeacherHomeworkView.as_view(), name='teacher-homework'),
    path('homework/student/', StudentHomeworkView.as_view(), name='student-homework'),
    path('homework/<int:homework_id>/overview/', HomeworkOverviewView.as_view(), name='homework-overview'),
    path('homework/<int:homework_id>/submit/', HomeworkSubmitView.as_view(), name='homework-submit'),
    path('homework/<int:homework_id>/result/', HomeworkResultView.as_view(), name='homework-result'),
    path('homework/<int:homework_id>/', HomeworkDeleteView.as_view(), name='homework-delete'),

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
    path('groups/<int:group_id>/students/<int:student_id>/', RemoveStudentFromGroupView.as_view(), name='remove-student'),

    path('messages/send/',SendMessageView.as_view(), name='send_message'),
    path('messages/conversation/', GetConversationView.as_view(), name='get_conversation'),
]
