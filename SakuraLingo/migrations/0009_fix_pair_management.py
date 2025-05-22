from django.db import migrations


def cleanup_invalid_lesson_exercises(apps, schema_editor):
    """Clean up lesson exercises that reference non-existent exercises or library pairs"""
    LessonsExercises = apps.get_model('SakuraLingo', 'LessonsExercises')
    ExerciseMatch = apps.get_model('SakuraLingo', 'ExerciseMatch')
    ExerciseFreetext = apps.get_model('SakuraLingo', 'ExerciseFreetext')
    ExerciseMultiChoice = apps.get_model('SakuraLingo', 'ExerciseMultiChoice')

    # Remove lesson exercises that reference library pairs (single-pair exercises)
    for le in LessonsExercises.objects.filter(exercise_type='pair-match'):
        try:
            exercise = ExerciseMatch.objects.get(id=le.exercise_id)
            pair_count = exercise.exercisematchoptions_set.count()
            if pair_count < 2:  # It's a library pair, not a real exercise
                le.delete()
        except ExerciseMatch.DoesNotExist:
            le.delete()

    # Remove lesson exercises that reference non-existent freetext exercises
    for le in LessonsExercises.objects.filter(exercise_type='freetext'):
        if not ExerciseFreetext.objects.filter(id=le.exercise_id).exists():
            le.delete()

    # Remove lesson exercises that reference non-existent multichoice exercises
    for le in LessonsExercises.objects.filter(exercise_type='multi-choice'):
        if not ExerciseMultiChoice.objects.filter(id=le.exercise_id).exists():
            le.delete()


def reverse_cleanup(apps, schema_editor):
    """Nothing to reverse"""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('SakuraLingo', '0008_lesson_updates'),
    ]

    operations = [
        migrations.RunPython(cleanup_invalid_lesson_exercises, reverse_cleanup),
    ]