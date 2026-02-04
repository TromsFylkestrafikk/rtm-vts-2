from django.db import models
from django.contrib.gis.db import models as gis_models # Import GeoDjango models
from django.utils import timezone

class ApiMetadata(models.Model):
    """
    Model to store metadata related to API interactions.
    """
    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()

    def __str__(self):
        return f"{self.key}: {self.value}"


class VtsSituation(models.Model):
    """
    Model to store transit situation information fetched from the VTS API,
    using GeoDjango fields for spatial data.
    """
    situation_id = models.CharField(max_length=255, unique=True)
    version = models.CharField(max_length=255)
    creation_time = models.DateTimeField(default=timezone.now)
    version_time = models.DateTimeField(null=True, blank=True)
    probability_of_occurrence = models.CharField(max_length=255, null=True, blank=True)
    severity = models.CharField(max_length=255, null=True, blank=True)
    source_country = models.CharField(max_length=255, null=True, blank=True)
    source_identification = models.CharField(max_length=255, null=True, blank=True)
    source_name = models.CharField(max_length=255, null=True, blank=True)
    source_type = models.CharField(max_length=255, null=True, blank=True)
    validity_status = models.CharField(max_length=255, null=True, blank=True)
    overall_start_time = models.DateTimeField(null=True, blank=True)
    overall_end_time = models.DateTimeField(null=True, blank=True)
    location = gis_models.PointField(srid=4326, null=True, blank=True, help_text="Primary point location (SRID 4326 WGS84)")
    path = gis_models.LineStringField(srid=4326, null=True, blank=True, help_text="LineString path from posList (SRID 4326 WGS84)")
    location_description = models.TextField(null=True, blank=True)
    road_number = models.CharField(max_length=255, null=True, blank=True)
    area_name = models.CharField(max_length=255, null=True, blank=True)
    transit_service_information = models.TextField(null=True, blank=True)
    transit_service_type = models.CharField(max_length=255, null=True, blank=True)
    pos_list_raw = models.TextField(null=True, blank=True, help_text="Raw posList string from XML for reference/debugging")
    comment = models.TextField(null=True, blank=True)
    filter_used=models.TextField(null=True,blank=True)

    def __str__(self):
        service_info = f"{self.road_number} - {self.transit_service_type}" if self.road_number else f"{self.transit_service_type}"
        location_info = f"at {self.location.y:.4f}, {self.location.x:.4f}" if self.location else "at unknown location"
        return f"{service_info} ({self.transit_service_information or 'No details'}) {location_info}"



class BusRoute(models.Model):
    """
    Stores the static geometry (path) of a specific bus route line.
    """
    # Primary Key (id) is added automatically by Django
    route_id = models.CharField(
        max_length=50, # Adjust max_length if route IDs can be longer
        db_index=True, # Index for faster lookups if needed
        null=True,     # <--- Add temporarily
        blank=True,    # <--- Add temporarily (good practice with null=True)
        help_text="Unique identifier for the bus route (e.g., '100', 'TFT:Line:34') from the source data"
    )
    path = gis_models.LineStringField(
        srid=4326,
        help_text="Route geometry as a LineString (SRID 4326 WGS84)"
    )
    version = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Version identifier for this route data (if provided by source)"
    )
    last_updated = models.DateTimeField(
        default=timezone.now,
        help_text="When this route information was last updated/imported"
    )

    def __str__(self):
        # Using the primary key as a simple identifier
        return f"Bus Route {self.route_id} (ID: {self.pk})"

    class Meta:
        verbose_name = "Bus Route"
        verbose_name_plural = "Bus Routes"
        ordering = ['route_id']

class DetectedCollision(models.Model):
    """
    Stores pre-calculated collision instances between VtsSituation points
    and BusRoute paths. Populated by a background task/management command.
    """
    transit_information = models.ForeignKey(
        VtsSituation,
        on_delete=models.CASCADE, # Or models.SET_NULL if you want to keep record if VTS msg deleted
        related_name='detected_collisions',
        db_index=True
    )
    bus_route = models.ForeignKey(
        BusRoute,
        on_delete=models.CASCADE,
        related_name='detected_collisions',
        db_index=True
    )
    # Store the coordinates of the transit point AT THE TIME of detection
    transit_lon = models.FloatField()
    transit_lat = models.FloatField()
    # Store when this collision record was created (when the check was run)
    detection_timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    tolerance_meters = models.IntegerField(default=50)
    unique_together = ('transit_information', 'bus_route')
    published_to_mqtt = models.BooleanField(
        default=False,
        db_index=True, # Index for faster querying of unpublished items
        help_text="Flag indicating if this collision has been published via MQTT."
    )
    class Meta:
        verbose_name = "Detected Collision"
        verbose_name_plural = "Detected Collisions"
        # Ensure a VTS message isn't listed multiple times for the same route from the same check run
        # Note: This assumes you clear old data before inserting new.
        # If updating, you might need a different constraint or logic.
        unique_together = ('transit_information', 'bus_route')
        ordering = ['-detection_timestamp', 'transit_information']

    def __str__(self):
        published_status = "[Published]" if self.published_to_mqtt else "[New]"
        return f"Collision {published_status}: Transit {self.transit_information_id} near Route {self.bus_route_id} detected at {self.detection_timestamp}"