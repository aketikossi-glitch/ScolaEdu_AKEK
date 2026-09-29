from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.redirection, name='redirection'),
    path('admin-principal/', views.admin_principal, name='admin_principal'),
    path('chef-etablissement/', views.chef_etablissement, name='chef_etablissement'),
    path('enseignant/', views.enseignant_dashboard, name='enseignant_dashboard'),
]
