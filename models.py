
from django.db import models
from datetime import timedelta
from django.utils import timezone
from django.conf import settings


class Ticket(models.Model):
    CATEGORY_CHOICES = [
        ('Network', 'Network'),
        ('Hardware', 'Hardware'),
        ('Software', 'Software'),
        ('Account', 'Account'),
        ('Other', 'Other'),
    ]

    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]

    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    ]
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tickets"
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    user_name = models.CharField(max_length=100)

    # Assign a ticket to a registered user
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tickets'
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )

    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='Medium'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Open'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    @property
    def sla_deadline(self):
        """Calculate the SLA deadline from ticket priority."""
        sla_hours = {
            "High": 4,
            "Medium": 24,
            "Low": 72,
        }

        hours = sla_hours.get(self.priority, 24)
        return self.created_at + timedelta(hours=hours)

    @property
    def is_overdue(self):
        """Check whether an unresolved ticket has exceeded its SLA."""
        if self.status == "Resolved":
            return False

        return timezone.now() > self.sla_deadline

    @property
    def sla_status(self):
        """Return the current SLA status."""
        if self.status == "Resolved":
            return "Resolved"

        if self.is_overdue:
            return "Overdue"

        return "On Track"


class TicketComment(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments"
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="helpdesk_comments"
    )

    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.ticket.title}"


class TicketActivity(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="activities"
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="helpdesk_activities"
    )

    action = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.ticket.title}"

class UserProfile(models.Model):

    ROLE_CHOICES = [
        ("ADMIN", "Admin"),
        ("AGENT", "Agent"),
        ("REQUESTER", "Requester"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="REQUESTER"
    )
    notify_ticket_assigned = models.BooleanField(default=True)
    notify_status_updates = models.BooleanField(default=True)
    notify_comments = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
