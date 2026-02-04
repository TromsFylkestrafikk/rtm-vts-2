import os
import django
import logging
from django.core.management.base import BaseCommand
from map.models import TransitInformation, ApiMetadata

# Set up Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "my_project.settings")
django.setup()

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Delete all data from TransitInformation and ApiMetadata tables."

    def handle(self, *args, **kwargs):
        try:
            # Delete all data from TransitInformation
            transit_count = TransitInformation.objects.count()
            TransitInformation.objects.all().delete()
            logger.info(f"Deleted {transit_count} records from TransitInformation.")
            
            # Delete all data from ApiMetadata
            metadata_count = ApiMetadata.objects.count()
            ApiMetadata.objects.all().delete()
            logger.info(f"Deleted {metadata_count} records from ApiMetadata.")

            self.stdout.write(self.style.SUCCESS("Successfully deleted all transit data."))
        except Exception as e:
            logger.error(f"Error while deleting data: {e}")
            self.stdout.write(self.style.ERROR(f"Error while deleting data: {e}"))
