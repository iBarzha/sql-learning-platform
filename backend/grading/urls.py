from django.urls import path

from .views import CriteriaCatalogView

urlpatterns = [
    path('criteria/', CriteriaCatalogView.as_view(), name='grading-criteria'),
]
