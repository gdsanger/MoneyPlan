from django.urls import path
from . import views

app_name = 'attachments'

urlpatterns = [
    path('upload/<str:app_label>/<str:model_name>/<int:object_id>/',
         views.upload_attachment, name='upload'),
    path('list/<str:app_label>/<str:model_name>/<int:object_id>/',
         views.list_attachments, name='list'),
    path('delete/<int:attachment_id>/',
         views.delete_attachment_view, name='delete'),
]
