from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .criteria import catalog_payload


class CriteriaCatalogView(APIView):
    """General criteria an instructor can enable for an exercise."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(catalog_payload())
