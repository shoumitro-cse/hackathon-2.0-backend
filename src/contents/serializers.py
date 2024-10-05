from rest_framework import serializers

from contents.models import Content, Author, Tag, ContentTag


# For Reading the data from the DB
class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = '__all__'


class ContentBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Content
        fields = '__all__'


class ContentDataSerializer(ContentBaseSerializer):
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["total_engagement"] = instance.like_count + instance.comment_count + instance.share_count
        data["engagement_rate"] = data["total_engagement"] / instance.view_count if instance.view_count > 0 else 0
        data["author"] = AuthorSerializer(instance.author).data
        return data


class ContentDataPostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer()

    class Meta:
        model = Content
        fields = '__all__'

    def create(self, validated_data):
        author_data = validated_data.pop("author")
        author, _ = Author.objects.get_or_create(
            unique_id=author_data["unique_external_id"],
            defaults={
                "username": author_data["unique_name"],
                "name": author_data["full_name"],
                "url": author_data["url"],
                "title": author_data["title"],
            }
        )

        content, created = Content.objects.update_or_create(
            unique_id=validated_data["unq_external_id"],
            defaults={
                "author": author,
                "title": validated_data["title"],
                "like_count": validated_data["stats"]["likes"],
                "comment_count": validated_data["stats"]["comments"],
                "share_count": validated_data["stats"]["shares"],
                "view_count": validated_data["stats"]["views"],
            }
        )

        # Handle hashtags
        for tag_name in validated_data.get("hashtags", []):
            tag, _ = Tag.objects.get_or_create(name=tag_name)
            ContentTag.objects.get_or_create(content=content, tag=tag)

        return content


class ContentSerializer(serializers.Serializer):
    author = AuthorSerializer(read_only=True)
    content = ContentBaseSerializer(read_only=True)


# For Writing the data from third party api to our database
class StatCountSerializer(serializers.Serializer):
    """
    `likes`    : Content -> like_count
    `comments` : Content -> comment_count
    `views`    : Content -> view_count
    `shares`   : Content -> share_count
    """
    likes = serializers.IntegerField()
    comments = serializers.IntegerField()
    views = serializers.IntegerField()
    shares = serializers.IntegerField()


class AuthorPostSerializer(serializers.Serializer):
    """
    unique_name        : Author -> username
    full_name          : Author -> name
    unique_external_id : Author -> unique_id
    url                : Author -> url
    title              : Author -> title
    big_metadata       : Author -> big_metadata
    secret_value       : Author -> secret_value
    """
    unique_name = serializers.CharField()  # Unique name is username
    full_name = serializers.CharField()  # Full name is name
    unique_external_id = serializers.CharField()  # Unique id
    url = serializers.CharField()  # URL of the author
    title = serializers.CharField()  # Title of the author
    big_metadata = serializers.JSONField()  # Metadata
    secret_value = serializers.JSONField()  # Secret value


class ContentPostSerializer(serializers.Serializer):
    unq_external_id = serializers.CharField(required=True)  # Unique id
    stats = StatCountSerializer(required=True)
    author = AuthorPostSerializer(required=True)
    big_metadata = serializers.JSONField()
    secret_value = serializers.JSONField()
    thumbnail_view_url = serializers.CharField(required=True)
    title = serializers.CharField(required=True)
    hashtags = serializers.ListField(child=serializers.CharField())
    timestamp = serializers.DateTimeField(required=True)
