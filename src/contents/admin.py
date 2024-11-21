from django.contrib import admin
from .models import MegaEcommerce, Content, ContentTag, Author, Tag


admin.site.register(Content)
admin.site.register(ContentTag)
admin.site.register(Author)
admin.site.register(Tag)
admin.site.register(MegaEcommerce)
