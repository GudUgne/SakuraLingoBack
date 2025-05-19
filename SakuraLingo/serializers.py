from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import User, ExerciseMatch, ExerciseMatchOptions, Group, GroupsStudents, Chat

class UserSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']

class UserUpdateSerializer(serializers.ModelSerializer):
    # Write-only fields for password change
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
        # If they're changing password, ensure they provided the current one and it's correct
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
        # Pop off password fields so super().update() won't try to write them directly
        new_pw = validated_data.pop('password', None)
        validated_data.pop('current_password', None)

        # Update other fields (first_name, last_name, etc.)
        instance = super().update(instance, validated_data)

        # Now set the new password (if requested)
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

        """Create user with hashed password"""
        user = User.objects.create_user(**validated_data)  # Uses Django's create_user method for hashing
        user.verification_status = not is_teacher  # Students auto-verified; teachers require manual check
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

class ExerciseMatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseMatch
        fields = '__all__'

class ExerciseMatchOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExerciseMatchOptions
        fields = '__all__'

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


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = '__all__'