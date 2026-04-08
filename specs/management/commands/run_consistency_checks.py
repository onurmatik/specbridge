from django.core.management.base import BaseCommand

from projects.models import Project
from specs.consistency import run_project_consistency


class Command(BaseCommand):
    help = "Run OpenAI-backed consistency checks for one or more projects."

    def add_arguments(self, parser):
        parser.add_argument("--project", dest="project_slug", help="Only run checks for the given project slug.")

    def handle(self, *args, **options):
        queryset = Project.objects.order_by("slug")
        if options["project_slug"]:
            queryset = queryset.filter(slug=options["project_slug"])

        if not queryset.exists():
            self.stdout.write(self.style.WARNING("No projects matched the requested scope."))
            return

        for project in queryset:
            run = run_project_consistency(project, trigger="management_command")
            if run.status == "completed":
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{project.slug}: completed with {run.issue_count} issue(s) via {run.provider}:{run.model}"
                    )
                )
            else:
                self.stdout.write(self.style.WARNING(f"{project.slug}: failed - {run.error_message}"))
