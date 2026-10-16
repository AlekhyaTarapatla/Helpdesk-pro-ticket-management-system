
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Count
from django.contrib.auth import (
    authenticate,
    login,
    logout,
    get_user_model,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .models import Ticket, TicketActivity, TicketComment, UserProfile
from .forms import CustomUserCreationForm, TicketForm, TicketCommentForm, UserDetailsForm, NotificationPreferencesForm
from django.contrib.auth.forms import PasswordChangeForm

# --------------------------------------------------
# USER ROLE HELPERS
# --------------------------------------------------

def get_user_role(user):
    """Return the user's application role."""

    if user.is_superuser:
        return "ADMIN"

    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": "REQUESTER"},
    )

    return profile.role


def get_visible_tickets(user):
    """Return only tickets the current user is allowed to view."""

    role = get_user_role(user)

    if role == "ADMIN":
        return Ticket.objects.all()

    if role == "AGENT":
        return Ticket.objects.filter(assignee=user)

    return Ticket.objects.filter(created_by=user)


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@login_required
def dashboard(request):
    role = get_user_role(request.user)

    # Each role sees only the tickets they are allowed to access.
    all_tickets = get_visible_tickets(request.user)

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()

    valid_statuses = [
        choice[0] for choice in Ticket.STATUS_CHOICES
    ]

    if status == "all" or status not in valid_statuses:
        status = ""

    tickets = all_tickets

    if status:
        tickets = tickets.filter(status=status)

    if query:
        tickets = tickets.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(user_name__icontains=query)
            | Q(category__icontains=query)
        )

    tickets = tickets.order_by("-created_at")

    # Only Admins can assign tickets.
    User = get_user_model()

    if role == "ADMIN":
        team_members = User.objects.filter(
            is_active=True,
            profile__role="AGENT",
        ).order_by("username")
    else:
        team_members = User.objects.none()

    context = {
        "tickets": tickets,
        "query": query,
        "selected_status": status,
        "team_members": team_members,
        "user_role": role,

        # Statistics use the same role-specific ticket queryset.
        "total_tickets": all_tickets.count(),
        "open_tickets": all_tickets.filter(
            status="Open"
        ).count(),
        "progress_tickets": all_tickets.filter(
            status="In Progress"
        ).count(),
        "resolved_tickets": all_tickets.filter(
            status="Resolved"
        ).count(),
    }

    return render(request, "tickets/dashboard.html", context)


# --------------------------------------------------
# UPDATE TICKET STATUS
# --------------------------------------------------

@login_required
@require_POST
def update_ticket_status(request, ticket_id):
    role = get_user_role(request.user)

    # Requesters cannot change ticket status.
    if role not in ("ADMIN", "AGENT"):
        messages.error(
            request,
            "You do not have permission to update ticket status.",
        )
        return redirect("dashboard")

    # Admins can update any ticket.
    # Agents can update only tickets assigned to them.
    if role == "ADMIN":
        ticket_queryset = Ticket.objects.all()
    else:
        ticket_queryset = Ticket.objects.filter(
            assignee=request.user
        )

    ticket = get_object_or_404(ticket_queryset, pk=ticket_id)

    new_status = request.POST.get("status", "").strip()

    valid_statuses = [
        choice[0] for choice in Ticket.STATUS_CHOICES
    ]

    if new_status not in valid_statuses:
        messages.error(request, "Please select a valid status.")
        return redirect("ticket_detail", ticket_id=ticket.pk)

    old_status = ticket.status

    if old_status != new_status:
        ticket.status = new_status
        ticket.save(update_fields=["status"])

        TicketActivity.objects.create(
            ticket=ticket,
            actor=request.user,
            action="Status changed",
            description=(
                f"Status changed from {old_status} "
                f"to {new_status}."
            ),
        )

        messages.success(
            request,
            "Ticket status updated successfully.",
        )
    else:
        messages.info(
            request,
            "The ticket already has that status.",
        )

    return redirect("ticket_detail", ticket_id=ticket.pk)


# --------------------------------------------------
# ASSIGN TICKET - ADMIN ONLY
# --------------------------------------------------

@login_required
@require_POST
def assign_ticket(request, ticket_id):
    if get_user_role(request.user) != "ADMIN":
        messages.error(
            request,
            "Only Admins can assign or reassign tickets.",
        )
        return redirect("dashboard")

    ticket = get_object_or_404(Ticket, pk=ticket_id)

    assignee_id = request.POST.get("assignee_id", "").strip()

    if not assignee_id:
        if ticket.assignee is not None:
            old_username = ticket.assignee.username

            ticket.assignee = None
            ticket.save(update_fields=["assignee"])

            TicketActivity.objects.create(
                ticket=ticket,
                actor=request.user,
                action="Ticket unassigned",
                description=(
                    f"Assignment removed from {old_username}."
                ),
            )

            messages.success(
                request,
                "Ticket is now unassigned.",
            )
        else:
            messages.info(
                request,
                "This ticket is already unassigned.",
            )

        return redirect("dashboard")

    User = get_user_model()

    try:
        assignee = User.objects.get(
            pk=assignee_id,
            is_active=True,
            profile__role="AGENT",
        )
    except (User.DoesNotExist, ValueError, TypeError):
        messages.error(
            request,
            "Please select a valid active Agent.",
        )
        return redirect("dashboard")

    old_assignee = ticket.assignee

    if old_assignee != assignee:
        ticket.assignee = assignee
        ticket.save(update_fields=["assignee"])

        if old_assignee:
            description = (
                f"Ticket reassigned from "
                f"{old_assignee.username} to {assignee.username}."
            )
            action = "Ticket reassigned"
        else:
            description = (
                f"Ticket assigned to {assignee.username}."
            )
            action = "Ticket assigned"

        TicketActivity.objects.create(
            ticket=ticket,
            actor=request.user,
            action=action,
            description=description,
        )

        messages.success(
            request,
            f"Ticket assigned to {assignee.username}.",
        )
    else:
        messages.info(
            request,
            f"Ticket is already assigned to {assignee.username}.",
        )

    return redirect("dashboard")


# --------------------------------------------------
# CREATE TICKET
# --------------------------------------------------

@login_required
def create_ticket(request):
    if request.method == "POST":
        form = TicketForm(request.POST)

        if form.is_valid():
            ticket = form.save(commit=False)

            # Record the logged-in user as the ticket creator.
            ticket.created_by = request.user
            ticket.user_name = request.user.username

            ticket.save()
            form.save_m2m()

            TicketActivity.objects.create(
                ticket=ticket,
                actor=request.user,
                action="Ticket created",
                description=(
                    f"Ticket '{ticket.title}' was created."
                ),
            )

            messages.success(
                request,
                "Ticket created successfully.",
            )
            return redirect("dashboard")
    else:
        form = TicketForm()

    return render(
        request,
        "tickets/create_ticket.html",
        {"form": form},
    )


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)

            # All roles use the same URL.
            # The dashboard selects the correct tickets by role.
            return redirect("dashboard")

        messages.error(
            request,
            "Invalid username or password.",
        )

    return render(request, "tickets/login.html")


# --------------------------------------------------
# REGISTER
# --------------------------------------------------

def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()

            # Ensure a profile exists for the new account.
            UserProfile.objects.get_or_create(
                user=user,
                defaults={"role": "REQUESTER"},
            )

            messages.success(
                request,
                "Account created successfully! Please log in.",
            )
            return redirect("login")
    else:
        form = CustomUserCreationForm()

    return render(
        request,
        "tickets/register.html",
        {"form": form},
    )


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@login_required
def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("login")

    return redirect("dashboard")


# --------------------------------------------------
# TICKET DETAILS
# --------------------------------------------------

@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(
        get_visible_tickets(request.user),
        pk=ticket_id,
    )

    comments = ticket.comments.select_related(
        "author"
    ).all()

    activities = ticket.activities.select_related(
        "actor"
    ).all()

    comment_form = TicketCommentForm()

    context = {
        "ticket": ticket,
        "comments": comments,
        "activities": activities,
        "comment_form": comment_form,
        "user_role": get_user_role(request.user),
    }

    return render(
        request,
        "tickets/ticket_detail.html",
        context,
    )


# --------------------------------------------------
# ADD COMMENT
# --------------------------------------------------

@login_required
@require_POST
def add_ticket_comment(request, ticket_id):
    ticket = get_object_or_404(
        get_visible_tickets(request.user),
        pk=ticket_id,
    )

    form = TicketCommentForm(request.POST)

    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        comment.save()

        TicketActivity.objects.create(
            ticket=ticket,
            actor=request.user,
            action="Comment added",
            description=(
                f"{request.user.username} added a comment."
            ),
        )

        messages.success(
            request,
            "Comment added successfully.",
        )
    else:
        messages.error(
            request,
            "Please enter a valid comment.",
        )

    return redirect(
        "ticket_detail",
        ticket_id=ticket.pk,
    )

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

@login_required
def settings_view(request):
    role = get_user_role(request.user)

    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"role": "REQUESTER"},
    )

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "profile":
            profile_form = UserDetailsForm(
                request.POST,
                instance=request.user,
            )

            if profile_form.is_valid():
                profile_form.save()
                messages.success(
                    request,
                    "Profile updated successfully.",
                )
                return redirect("settings")

            notification_form = NotificationPreferencesForm(
                instance=profile
            )
            password_form = PasswordChangeForm(user=request.user)

        elif form_type == "notifications":
            notification_form = NotificationPreferencesForm(
                request.POST,
                instance=profile,
            )

            if notification_form.is_valid():
                notification_form.save()
                messages.success(
                    request,
                    "Notification preferences saved.",
                )
                return redirect("settings")

            profile_form = UserDetailsForm(
                instance=request.user
            )
            password_form = PasswordChangeForm(user=request.user)

        elif form_type == "password":
            password_form = PasswordChangeForm(
                user=request.user,
                data=request.POST,
            )

            if password_form.is_valid():
                user = password_form.save()

                # Keep the user logged in after changing password.
                update_session_auth_hash(request, user)

                messages.success(
                    request,
                    "Your password has been changed successfully.",
                )
                return redirect("settings")

            profile_form = UserDetailsForm(
                instance=request.user
            )
            notification_form = NotificationPreferencesForm(
                instance=profile
            )

        else:
            return redirect("settings")

    else:
        profile_form = UserDetailsForm(instance=request.user)
        notification_form = NotificationPreferencesForm(
            instance=profile
        )
        password_form = PasswordChangeForm(user=request.user)

    context = {
        "user_role": role,
        "profile_form": profile_form,
        "notification_form": notification_form,
        "password_form": password_form,
    }

    return render(
        request,
        "tickets/settings.html",
        context,
    )


@login_required
def reports_view(request):
    role = get_user_role(request.user)

    # Respect the ticket visibility rules for each role.
    visible_tickets = get_visible_tickets(request.user)

    total_tickets = visible_tickets.count()
    open_tickets = visible_tickets.filter(status="Open").count()
    in_progress_tickets = visible_tickets.filter(
        status="In Progress"
    ).count()
    resolved_tickets = visible_tickets.filter(
        status="Resolved"
    ).count()

    # Breakdown by status, priority, and category.
    status_data = list(
        visible_tickets.values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )

    priority_data = list(
        visible_tickets.values("priority")
        .annotate(total=Count("id"))
        .order_by("priority")
    )

    category_data = list(
        visible_tickets.values("category")
        .annotate(total=Count("id"))
        .order_by("category")
    )

    # Find maximum values for progress bars in the template.
    max_status_count = max(
        (item["total"] for item in status_data),
        default=1,
    )
    max_priority_count = max(
        (item["total"] for item in priority_data),
        default=1,
    )
    max_category_count = max(
        (item["total"] for item in category_data),
        default=1,
    )

    recent_tickets = visible_tickets.order_by(
        "-created_at"
    )[:8]

    context = {
        "user_role": role,
        "total_tickets": total_tickets,
        "open_tickets": open_tickets,
        "in_progress_tickets": in_progress_tickets,
        "resolved_tickets": resolved_tickets,
        "status_data": status_data,
        "priority_data": priority_data,
        "category_data": category_data,
        "max_status_count": max_status_count,
        "max_priority_count": max_priority_count,
        "max_category_count": max_category_count,
        "recent_tickets": recent_tickets,
    }

    return render(request, "tickets/reports.html", context)
