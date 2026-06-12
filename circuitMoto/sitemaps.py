from django.contrib.sitemaps import Sitemap
from .models import Circuit

class CircuitSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Circuit.objects.filter(statut="PUBLIE")

    def lastmod(self, obj):
        # Horodatage: on prend ce qui existe sans casser
        return getattr(obj, "modifie_le", None) or getattr(obj, "updated_at", None) or getattr(obj, "cree_le", None)