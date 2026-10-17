from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('drivers', '0003_alter_driver_options_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='driver',
            name='bank_account_number',
        ),
        migrations.RemoveField(
            model_name='driver',
            name='bank_ifsc_code',
        ),
        migrations.RemoveField(
            model_name='driver',
            name='upi_id',
        ),
    ]
