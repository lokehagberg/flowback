from rest_framework import serializers

from flowback.user.serializers import BasicUserSerializer
from flowback.files.serializers import FileSerializer


class _MessageSerializerTemplate(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    user = BasicUserSerializer()
    channel_id = serializers.IntegerField()
    message = serializers.CharField()
    attachments = FileSerializer(many=True, source='attachments.file_collection.filesegment_set', allow_null=True)


class BasicMessageSerializer(_MessageSerializerTemplate):
    parent_id = serializers.IntegerField(required=False)


class MessageSerializer(_MessageSerializerTemplate):
    parent = BasicMessageSerializer()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()
    active = serializers.BooleanField()
