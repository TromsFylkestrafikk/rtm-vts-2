
from django.core.management.base import BaseCommand, CommandError
from django.core import management
import time

class Command(BaseCommand):
    """
    Runs the required sequence of commands for periodic VTS data processing and publishing.
    1. Fetches VTS situations.
    2. Calculates collisions (without clearing previous ones).
    3. Publishes new collisions via MQTT.
    """
    help = 'Runs fetch_vts_situations, calculate_and_store_collisions --no-clear, and publish_new_collisions sequentially.'

    def handle(self, *args, **options):
        start_time = time.time()
        self.stdout.write(self.style.SUCCESS("Starting periodic VTS update sequence..."))

        commands_to_run = [
            {'name': 'fetch_vts_situations', 'args': {}},
            {'name': 'calculate_and_store_collisions', 'args': {'no_clear': True}}, # Pass --no-clear as True
            {'name': 'publish_new_collisions', 'args': {}},
        ]

        for cmd_info in commands_to_run:
            cmd_name = cmd_info['name']
            cmd_args = cmd_info['args']
            arg_string = ' '.join([f'--{k}' for k, v in cmd_args.items() if v is True]) # Just for logging display

            self.stdout.write(f"\nRunning: {cmd_name} {arg_string}...")
            try:
                # Use django.core.management.call_command to run other commands
                # Pass boolean flags like --no-clear as keyword arguments set to True
                management.call_command(cmd_name, **cmd_args)
                self.stdout.write(self.style.SUCCESS(f"-> {cmd_name} completed successfully."))

            except CommandError as e:
                self.stderr.write(self.style.ERROR(f"Error during {cmd_name}: {e}"))
                # Decide if you want to stop the sequence on error.
                # For a cron job, it might be better to log and potentially continue,
                # but calculate depends on fetch, and publish depends on calculate.
                # Let's stop if fetch or calculate fails. Publish failure might be less critical to stop for.
                if cmd_name in ['fetch_vts_situations', 'calculate_and_store_collisions']:
                     self.stderr.write(self.style.ERROR("Aborting sequence due to critical error."))
                     # Re-raise the error to make the overall command fail
                     raise e
                else:
                    # Log error for publish but continue to report overall finish time
                    self.stderr.write(self.style.WARNING(f"Continuing sequence despite error in {cmd_name}."))

            except Exception as e:
                # Catch any other unexpected errors
                self.stderr.write(self.style.ERROR(f"An unexpected error occurred during {cmd_name}: {e}"))
                if cmd_name in ['fetch_vts_situations', 'calculate_and_store_collisions']:
                    self.stderr.write(self.style.ERROR("Aborting sequence due to unexpected critical error."))
                    raise CommandError(f"Unexpected error in {cmd_name}") from e
                else:
                     self.stderr.write(self.style.WARNING(f"Continuing sequence despite unexpected error in {cmd_name}."))


        end_time = time.time()
        duration = end_time - start_time
        self.stdout.write(self.style.SUCCESS(f"\nPeriodic VTS update sequence finished in {duration:.2f} seconds."))