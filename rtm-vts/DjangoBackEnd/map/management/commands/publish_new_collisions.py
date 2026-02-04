"""
Django Management Command: publish_collisions

This command scans the database for newly detected collisions
(marked as not published to MQTT) and publishes their details
to a configured MQTT broker. It ensures that collision data
is disseminated in near real-time to subscribers interested
in specific routes, severities, or filters.
"""

import time
import json
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import transaction
from map.models import DetectedCollision # Assuming your model is in the 'map' app

try:
    import paho.mqtt.client as mqtt
    mqtt_available = True
except ImportError:
    mqtt_available = False

logger = logging.getLogger(__name__) # Use Django's logging setup

class Command(BaseCommand):
    """
    Connects to an MQTT broker and publishes details of DetectedCollision
    objects that have not yet been marked as published.

    This command performs the following steps:
    1. Checks for the availability of the 'paho-mqtt' library.
    2. Queries the database for `DetectedCollision` records where
       `published_to_mqtt` is False, ordering by detection time.
    3. Connects to the MQTT broker specified in Django settings.
    4. Iterates through the unpublished collisions.
    5. For each collision:
       a. Constructs a JSON payload containing relevant details.
       b. Constructs a hierarchical MQTT topic based on route, severity, and filter.
       c. Publishes the payload to the topic.
       d. Waits for publish confirmation from the broker.
    6. After attempting to publish all collisions, it updates the
       `published_to_mqtt` flag to True in the database for all collisions
       that were successfully published and confirmed. This is done in a
       single atomic transaction.
    7. Disconnects from the MQTT broker.
    8. Logs progress and errors using Django's logging framework.
    """
    help = 'Checks for unpublished collisions and publishes them via MQTT.'

    def _sanitize_topic_segment(self, segment_value, placeholder='_unknown_'):
        """
        Sanitizes a string value to be safely used as an MQTT topic segment.

        MQTT topic segments cannot contain '+', '#', or '/'. This function
        replaces these characters with underscores. It also handles None or
        empty values by replacing them with a specified placeholder.

        Args:
            segment_value: The raw value to be sanitized (usually a string or None).
            placeholder (str): The string to use if segment_value is None or empty.

        Returns:
            str: The sanitized string suitable for use in an MQTT topic.
        """
        if not segment_value:
            return placeholder
        # Convert to string first to handle potential non-string types
        segment_str = str(segment_value)
        # Replace characters forbidden in topic segments
        sanitized = segment_str.replace('+', '_').replace('#', '_').replace('/', '_')
        # Ensure it's not empty after replacements if the original was just forbidden chars
        return sanitized if sanitized else placeholder

    def handle(self, *args, **options):
        """
        The main execution method called by Django's manage.py.

        Orchestrates the process of finding, publishing, and marking collisions.
        Handles MQTT connection, publishing loop, and database updates.
        Provides feedback to the console and logs detailed information.
        """
        start_time = time.time()
        self.stdout.write("Starting MQTT collision publisher...")

        # --- Prerequisite Checks ---
        if not mqtt_available:
            self.stderr.write(self.style.ERROR(
                "CRITICAL: 'paho-mqtt' library not found. "
                "Please install it (`pip install paho-mqtt`). Cannot publish."
            ))
            return

        # --- Configuration ---
        mqtt_broker_host = getattr(settings, 'MQTT_BROKER_HOST', None)
        mqtt_broker_port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
        mqtt_username = getattr(settings, 'MQTT_USERNAME', None)
        mqtt_password = getattr(settings, 'MQTT_PASSWORD', None)
        base_topic = getattr(settings, 'MQTT_BASE_COLLISION_TOPIC', 'vts/collisions')

        if not mqtt_broker_host:
            self.stderr.write(self.style.ERROR(
                "CRITICAL: MQTT_BROKER_HOST setting is not configured in settings.py. Cannot connect."
            ))
            return

        mqtt_client = None
        published_count = 0
        processed_count = 0
        db_update_failed_flag = False
        successfully_marked_ids = [] # Track IDs actually marked in DB

        # --- Find Unpublished Collisions ---
        try:
            # Important: select_related to avoid N+1 queries when accessing related fields
            # like transit_information and bus_route inside the loop.
            collisions_to_publish = DetectedCollision.objects.filter(
                published_to_mqtt=False
            ).select_related(
                'transit_information', 'bus_route'
            ).order_by('detection_timestamp') # Process oldest first for chronological order

            processed_count = collisions_to_publish.count()
            if not collisions_to_publish:
                self.stdout.write(self.style.SUCCESS("No new collisions found to publish."))
                # No need to connect to MQTT if there's nothing to send
                return

            self.stdout.write(f"Found {processed_count} unpublished collisions. Attempting to publish...")

        except Exception as e:
            logger.error(f"Database error fetching collisions: {e}", exc_info=True)
            self.stderr.write(self.style.ERROR(f"Database error fetching collisions: {e}. Aborting."))
            return

        # --- Connect to MQTT ---
        try:
            # Use V1 API for compatibility as shown in the original code
            mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

            # Set credentials if provided
            if mqtt_username and mqtt_password:
                mqtt_client.username_pw_set(mqtt_username, mqtt_password)
                self.stdout.write("Using MQTT username/password authentication.")
            elif mqtt_username:
                 self.stdout.write("Using MQTT username authentication (no password provided).")
            else:
                 self.stdout.write("Connecting to MQTT without authentication.")

            # Set connection timeout (default is often short)
            connect_timeout = 10 # seconds
            mqtt_client.connect(mqtt_broker_host, mqtt_broker_port, keepalive=60) # keepalive interval
            mqtt_client.loop_start() # Start background thread for network traffic & callbacks
            # Note: Actual connect timeout isn't directly settable here in paho V1 connect,
            # it's handled internally. loop_start handles reconnect logic.
            # We rely on the connect call raising an exception if immediate connection fails.
            # A short sleep might help confirm connection, but loop_start handles it.
            time.sleep(1) # Give a moment for the connection background thread
            if not mqtt_client.is_connected():
                 # Check connection status after starting loop
                 raise ConnectionRefusedError("MQTT client failed to connect after loop_start.")

            self.stdout.write(f"Successfully connected to MQTT Broker {mqtt_broker_host}:{mqtt_broker_port}")

        except ConnectionRefusedError as e:
            logger.error(f"MQTT Connection Refused: {e}", exc_info=True)
            self.stderr.write(self.style.ERROR(f"MQTT Connection Refused: {e}. Check host, port, credentials, and firewall."))
            if mqtt_client: mqtt_client.loop_stop() # Ensure loop stops if started partially
            return
        except Exception as e:
            logger.error(f"Could not connect to MQTT Broker: {e}", exc_info=True)
            self.stderr.write(self.style.ERROR(f"Could not connect to MQTT Broker: {e}. Aborting publish cycle."))
            if mqtt_client: mqtt_client.loop_stop() # Ensure loop stops
            return

        # --- Publish Loop ---
        ids_to_mark_published = [] # Store IDs confirmed published by the broker
        publish_failures = 0

        for collision in collisions_to_publish:
            try:
                # --- Prepare Payload ---
                # Ensure related objects exist before accessing attributes
                transit_info = collision.transit_information
                bus_route = collision.bus_route # Can be None if relation allows null

                payload = {
                    "event": "new_collision", # Type of event
                    "collision_id": collision.id,
                    "transit_id": collision.transit_information_id,
                    "route_id": collision.bus_route_id, # Foreign key value
                    "lon": collision.transit_lon,
                    "lat": collision.transit_lat,
                    "tolerance": collision.tolerance_meters,
                    "detected_at": collision.detection_timestamp.isoformat() if collision.detection_timestamp else None,
                    # Safely access related fields
                    "severity": transit_info.severity if transit_info else None,
                    "filter_used": transit_info.filter_used if transit_info else None,
                    "situation_id": transit_info.situation_id if transit_info else None,
                    "Bus_number": bus_route.route_id if bus_route else None, # Use the actual route identifier field
                    "comment": transit_info.comment if transit_info else None
                }

                # --- Serialize Payload ---
                try:
                    # ensure_ascii=False is important for non-English characters in comments etc.
                    payload_json = json.dumps(payload, ensure_ascii=False)
                except TypeError as e:
                    logger.error(f"Error serializing payload for collision {collision.id}: {e}. Data: {payload}", exc_info=True)
                    self.stderr.write(f"Error serializing payload for collision {collision.id}: {e}. Skipping.")
                    publish_failures += 1
                    continue # Skip this collision

                # --- Construct Topic ---
                bus_route_id_str = self._sanitize_topic_segment(payload["Bus_number"]) # Use the actual route ID from payload
                severity_str = self._sanitize_topic_segment(payload["severity"])
                filter_str = self._sanitize_topic_segment(payload["filter_used"])

                # Example: vts/collisions/route/101/severity/high/filter/some_filter
                topic = f"{base_topic}/route/{bus_route_id_str}/severity/{severity_str}/filter/{filter_str}"

                # --- Publish ---
                # Publish with QoS 1 (at least once delivery) for better reliability
                # QoS 2 (exactly once) is safer but higher overhead. QoS 0 (at most once) is fire-and-forget.
                qos = 1
                result_info = mqtt_client.publish(topic, payload_json, qos=qos)

                # Wait for acknowledgment for QoS 1 or 2
                # Timeout should be reasonable, e.g., 5 seconds.
                publish_timeout = 5.0
                try:
                     # wait_for_publish can raise an exception on timeout for some paho versions
                     # or just return without is_published() being true.
                    result_info.wait_for_publish(timeout=publish_timeout)
                except ValueError:
                    # Some paho-mqtt versions might raise ValueError if message delivery failed
                    logger.warning(f"MQTT publish confirmation error (ValueError) for collision {collision.id} to {topic}. Will retry next cycle.")
                    publish_failures += 1
                    continue # Don't mark as published
                except RuntimeError:
                     # Can be raised if loop isn't running, etc.
                    logger.warning(f"MQTT publish confirmation error (RuntimeError) for collision {collision.id} to {topic}. Will retry next cycle.")
                    publish_failures += 1
                    continue # Don't mark as published

                # Explicitly check if published after waiting
                if result_info.is_published():
                    published_count += 1
                    ids_to_mark_published.append(collision.id) # Add ID to list for bulk update later
                    logger.debug(f"Successfully published collision {collision.id} to {topic} (QoS {qos}, MID: {result_info.mid})")
                else:
                    # This path is taken if wait_for_publish timed out or failed silently
                    logger.warning(f"MQTT publish confirmation timed out or failed for collision {collision.id} (MID: {result_info.mid}) to topic {topic} after {publish_timeout}s. Will retry next cycle.")
                    publish_failures += 1
                    # DO NOT add to ids_to_mark_published if confirmation fails or times out

            except AttributeError as e:
                 # Catch errors if related objects (transit_info, bus_route) are None unexpectedly
                 logger.error(f"Error accessing attributes for collision {collision.id}: {e}. Check data integrity.", exc_info=True)
                 self.stderr.write(f"Data error for collision {collision.id}: {e}. Skipping.")
                 publish_failures += 1
            except Exception as pub_e:
                # Catch other potential errors during payload prep or publish call
                logger.error(f"Unexpected error during publish loop for collision {collision.id}: {pub_e}", exc_info=True)
                self.stderr.write(f"Unexpected error for collision {collision.id}: {pub_e}. Skipping.")
                publish_failures += 1
                # DO NOT add to ids_to_mark_published on error

        # --- Mark as Published in DB ---
        if ids_to_mark_published:
            self.stdout.write(f"Attempting to mark {len(ids_to_mark_published)} collisions as published in the database...")
            try:
                # Use a transaction to ensure atomicity: either all are marked or none are.
                with transaction.atomic():
                    updated_count = DetectedCollision.objects.filter(
                        id__in=ids_to_mark_published,
                        published_to_mqtt=False # Ensure we only update those not already marked
                    ).update(published_to_mqtt=True)

                successfully_marked_ids = ids_to_mark_published # If transaction succeeded
                if updated_count != len(ids_to_mark_published):
                    logger.warning(f"DB Update count mismatch: Expected {len(ids_to_mark_published)}, updated {updated_count}. Some might have been updated concurrently?")
                    # Still report the number successfully updated by *this* process.
                    self.stdout.write(f"Successfully marked {updated_count} collisions as published in the database.")
                else:
                    self.stdout.write(f"Successfully marked {updated_count} collisions as published in the database.")

            except Exception as db_e:
                 logger.error(f"Failed to mark collisions {ids_to_mark_published} as published in database: {db_e}", exc_info=True)
                 self.stderr.write(self.style.ERROR(f"CRITICAL: Failed to mark collisions as published: {db_e}. These collisions WILL be re-published on the next run."))
                 # Set flag to indicate DB update failure in summary
                 db_update_failed_flag = True
                 successfully_marked_ids = [] # Reset this list as the update failed

        elif published_count > 0:
             # This case should ideally not happen if publish succeeded but marking list is empty,
             # but good to log if it does.
             logger.warning("Published count > 0 but no IDs were queued for DB update. Check logic.")

        # --- Cleanup MQTT ---
        if mqtt_client and mqtt_client.is_connected():
            self.stdout.write("Disconnecting from MQTT Broker...")
            try:
                mqtt_client.loop_stop() # Stop the background thread cleanly
                mqtt_client.disconnect()
                self.stdout.write("Disconnected from MQTT Broker.")
            except Exception as e:
                 logger.warning(f"Error during MQTT disconnect: {e}", exc_info=True)
                 # Continue anyway, the connection will likely time out on the broker side.

        elif mqtt_client:
             # If client exists but isn't connected (e.g., initial connection failed after loop_start)
             try:
                 mqtt_client.loop_stop() # Attempt to stop loop just in case
             except Exception: pass # Ignore errors if loop wasn't running


        # --- Final Summary ---
        end_time = time.time()
        duration = end_time - start_time
        marked_count = len(successfully_marked_ids) # Use the list of IDs confirmed marked

        summary_message = (
            f"Publish cycle finished in {duration:.2f} seconds. "
            f"Collisions found: {processed_count}. "
            f"Successfully published (confirmed): {published_count}. "
            f"Failed to publish/confirm: {publish_failures}. "
            f"Successfully marked as published in DB: {marked_count}."
        )

        if db_update_failed_flag:
            self.stderr.write(self.style.ERROR(
                f"{summary_message} "
                f"WARNING: Database update failed for {len(ids_to_mark_published)} items; they will be retried."
            ))
        elif published_count != marked_count:
             # This implies a potential issue (e.g., publish confirmed but DB update failed, or logic error)
             self.stderr.write(self.style.WARNING(
                f"{summary_message} "
                f"WARNING: Mismatch between published count ({published_count}) and DB marked count ({marked_count}). Check logs."
             ))
        elif published_count == 0 and processed_count > 0:
             # If we processed items but published none
              self.stdout.write(self.style.WARNING(
                f"{summary_message} "
                f"Note: No collisions were successfully published in this run."
             ))
        else:
            # Success / Normal operation
            self.stdout.write(self.style.SUCCESS(summary_message))