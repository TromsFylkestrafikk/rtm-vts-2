"""
Django Management Command: update_collisions

This command recalculates potential collisions between VTS and defined
bus routes based on a specified proximity tolerance. It then updates the
`DetectedCollision` table in the database with the results.

By default, it clears all existing detected collisions before inserting the
newly calculated ones. An option exists to prevent clearing and only add
newly detected collisions not already present.
"""
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from map.models import DetectedCollision
from map.utils import calculate_collisions_for_storage # Import the calculation function
import logging
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Handles the recalculation and storage of detected collisions.

    It calls an external function `calculate_collisions_for_storage` to
    perform the geographic proximity analysis based on the provided tolerance.
    The results are then processed and stored in the `DetectedCollision` model.

    Key features:
    - Customizable proximity tolerance via command-line argument.
    - Option to clear existing collision data before inserting new results (default).
    - Option to preserve existing data and only insert new, unique collision pairs.
    - Uses `transaction.atomic` for database operations to ensure consistency.
    - Uses `bulk_create` for efficient insertion of new records.
    - Handles potential duplicate collision pairs (both against existing data
      if not clearing, and within the newly calculated batch).
    """
    help = 'Recalculates and updates the stored detected collisions between VTS points and bus routes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tolerance',
            type=int,
            # 300 meters can detect ferry abnormalies
            default=300, # Default tolerance if not specified
            help='Distance tolerance in meters for collision detection.',
        )
        parser.add_argument(
            '--no-clear',
            action='store_true',
            help='Do not clear existing collision data before inserting new data (use with caution).',
        )

    def handle(self, *args, **options):
        tolerance = options['tolerance']
        clear_existing = not options['no_clear']
        start_time = time.time()

        logger.info(f"Running update_collisions. Tolerance={tolerance}, Clear Existing Data={clear_existing}")
        self.stdout.write(f"Option --no-clear specified: {options['no_clear']}. Clear Existing Data set to: {clear_existing}")

        # --- Calculate New Collisions ---
        calculated_data = calculate_collisions_for_storage(tolerance)
        # ... (error checking for calculated_data) ...
        calculation_time = time.time()
        self.stdout.write(f"Calculation finished in {calculation_time - start_time:.2f} seconds. Found {len(calculated_data)} potential collisions.")

        created_count = 0
        skipped_count = 0 # For duplicates within calculation OR already existing

        # --- Database Operations ---
        try:
            with transaction.atomic():
                existing_pairs_set = set() # Initialize
                if clear_existing:
                    self.stdout.write("Clearing existing collision data...")
                    deleted_count, _ = DetectedCollision.objects.all().delete()
                    self.stdout.write(f"Deleted {deleted_count} old collision records.")
                else:
                    # --- If not clearing, get existing pairs to avoid re-inserting ---
                    self.stdout.write(self.style.WARNING("Skipping clearing. Fetching existing collision pairs..."))
                    # Fetch tuple pairs for efficient lookup
                    existing_pairs = DetectedCollision.objects.values_list(
                        'transit_information_id',
                        'bus_route_id'
                    )
                    existing_pairs_set = set(existing_pairs)
                    self.stdout.write(f"Found {len(existing_pairs_set)} existing pairs in the database.")
                    # --- End fetching existing pairs ---

                self.stdout.write("Preparing new collision data for storage...")
                collisions_to_create = []
                # Use a separate set to track pairs added *in this specific run*
                # to handle potential duplicates within calculated_data itself.
                seen_in_this_run = set()

                for data in calculated_data:
                    pair = (data['transit_id'], data['route_id'])

                    # --- Check 1: Already exists in DB (only if not clearing) ---
                    if not clear_existing and pair in existing_pairs_set:
                        skipped_count += 1
                        continue # Skip if it already exists in the database

                    # --- Check 2: Already added in this calculation run ---
                    if pair in seen_in_this_run:
                        # This handles duplicates *within* calculated_data
                        # Might indicate an issue in calculation logic if it happens often
                        logger.warning(f"Duplicate pair {pair} found within calculated_data. Skipping.")
                        skipped_count += 1
                        continue # Skip if already processed in this loop

                    # --- If new, add to create list and track ---
                    collisions_to_create.append(
                        DetectedCollision(
                            transit_information_id=data['transit_id'],
                            bus_route_id=data['route_id'],
                            transit_lon=data['transit_lon'],
                            transit_lat=data['transit_lat'],
                            tolerance_meters=tolerance
                            # published_to_mqtt defaults to False
                        )
                    )
                    seen_in_this_run.add(pair) # Track pair added in this run

                if collisions_to_create:
                    self.stdout.write(f"Bulk creating {len(collisions_to_create)} genuinely new collision records...")
                    created_objects = DetectedCollision.objects.bulk_create(collisions_to_create)
                    created_count = len(created_objects)
                    self.stdout.write(f"Successfully stored {created_count} new collision records (marked as unpublished).")
                else:
                     self.stdout.write("No genuinely new collision records found to store.")

        except Exception as e:
            logger.error(f"Database operation failed: {e}", exc_info=True) # Log traceback
            self.stderr.write(self.style.ERROR(f"Database operation failed: {e}"))

        end_time = time.time()
        self.stdout.write(self.style.SUCCESS(
            f"Collision update finished in {end_time - start_time:.2f} seconds. "
            f"Stored: {created_count}. Skipped existing/duplicates: {skipped_count}."
        ))