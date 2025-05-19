from django.contrib import admin
from .models import User, ExerciseMatch, Group, GroupsStudents

admin.site.register(User)
admin.site.register(ExerciseMatch)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'teacher')
    search_fields = ('name', 'teacher__username')


@admin.register(GroupsStudents)
class GroupsStudentsAdmin(admin.ModelAdmin):
    list_display = ('student', 'group', 'verification_status')
    list_filter = ('verification_status', 'group')
    search_fields = ('student__username', 'group__name')
