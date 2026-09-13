from django.urls import path

from . import views

app_name = 'feedback'

urlpatterns = [
    path('submit/', views.FeedbackSubmitAPIView.as_view(), name='feedback-submit'),
    path('', views.FeedbackListCreateAPIView.as_view(), name='feedback-list-create'),
    path('<uuid:pk>/', views.FeedbackRetrieveUpdateDestroyAPIView.as_view(), name='feedback-detail'),
]
