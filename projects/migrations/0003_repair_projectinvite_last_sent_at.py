from django.db import migrations


def ensure_last_sent_at_column(apps, schema_editor):
    table_name = "projects_projectinvite"
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        cursor.execute(f"PRAGMA table_info({table_name})")
        column_names = {row[1] for row in cursor.fetchall()}
        if "last_sent_at" in column_names:
            return
        cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "last_sent_at" datetime NULL')


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0002_projectinvite_last_sent_at"),
    ]

    operations = [
        migrations.RunPython(ensure_last_sent_at_column, migrations.RunPython.noop),
    ]
