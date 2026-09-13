from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .models import Feedback
from .serializers import FeedbackSerializer, FeedbackSubmitSerializer


class FeedbackListCreateAPIView(generics.ListCreateAPIView):
    queryset = Feedback.objects.select_related('order').all()
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]


class FeedbackRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Feedback.objects.select_related('order').all()
    serializer_class = FeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]


class FeedbackSubmitAPIView(generics.CreateAPIView):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSubmitSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback = serializer.save()
        return Response(
            {'id': str(feedback.id), 'message': 'Thank you for your feedback!'},
            status=status.HTTP_201_CREATED,
        )
