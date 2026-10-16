
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create/', views.create_ticket, name='create_ticket'),
    path('update-status/<int:ticket_id>/',views.update_ticket_status,name='update_ticket_status'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path("tickets/<int:ticket_id>/", views.ticket_detail,name="ticket_detail",),
    path("tickets/<int:ticket_id>/comments/",views.add_ticket_comment,name="add_ticket_comment",),
    path('tickets/<int:ticket_id>/assign/',views.assign_ticket,name='assign_ticket'),
    path("settings/", views.settings_view, name="settings"),
    path("reports/", views.reports_view, name="reports"),
]
