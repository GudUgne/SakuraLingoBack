from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('SakuraLingo', '0007_freetextsubmission'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lesson',
            name='jlpt_level',
            field=models.CharField(default='1-5', max_length=10),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='lesson_type',
            field=models.CharField(default='mixed', max_length=100),
        ),
        migrations.AlterField(
            model_name='lesson',
            name='exercise_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AlterUniqueTogether(
            name='lessonsexercises',
            unique_together={('lesson', 'exercise_id', 'exercise_type')},
        ),
    ]