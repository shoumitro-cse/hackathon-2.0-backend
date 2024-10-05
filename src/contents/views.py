from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from datetime import timedelta
from contents.models import Content, Author, Tag, ContentTag
from contents.serializers import ContentSerializer, ContentDataPostSerializer, ContentDataSerializer
from django.core.paginator import Paginator
from django.utils.timezone import now
from django.db.models.functions import Coalesce
from django.db.models import Q, Sum, Count, F, Case, When, FloatField


class ContentAPIView(APIView):

    def get(self, request):
        """
        TODO: Client is complaining about the app performance, the app is loading very slowly, our QA identified that
        this api is slow af. Make the api performant. Need to add pagination. But cannot use rest framework view set.
        As frontend, app team already using this api, do not change the api schema.
        Need to send some additional data as well,
        --------------------------------
        1. Total Engagement = like_count + comment_count + share_count
        2. Engagement Rate = Total Engagement / Views
        Users are complaining these additional data is wrong.
        Need filter support for client side. Add filters for (author_id, author_username, timeframe )
        For timeframe, the content's timestamp must be withing 'x' days.
        Example: api_url?timeframe=7, will get contents that has timestamp now - '7' days
        --------------------------------
        So things to do:
        1. Make the api performant
        2. Fix the additional data point in the schema
           - Total Engagement = like_count + comment_count + share_count
           - Engagement Rate = Total Engagement / Views
           - Tags: List of tags connected with the content
        3. Filter Support for client side
           - author_id: Author's db id
           - author_username: Author's username
           - timeframe: Content that has timestamp: now - 'x' days
           - tag_id: Tag ID
           - title (insensitive match IE: SQL `ilike %text%`)
        4. Must not change the inner api schema
        5. Remove metadata and secret value from schema
        6. Add pagination
           - Should have page number pagination
           - Should have items per page support in query params
           Example: `api_url?items_per_page=10&page=2`
       """

        query_params = request.query_params
        author_id = query_params.get('author_id', None)
        author_username = query_params.get('author_username', None)
        tag_id = query_params.get('tag_id', None)
        title = query_params.get('title', None)
        timeframe = query_params.get('timeframe', None)
        items_per_page = int(query_params.get('items_per_page', 10))
        page = int(query_params.get('page', 1))

        filters = Q()

        if author_id:
            filters &= Q(author_id=author_id)
        if author_username:
            filters &= Q(author__username__iexact=author_username)
        if tag_id:
            filters &= Q(contenttag__tag_id=tag_id)
        if title:
            filters &= Q(title__icontains=title)
        if timeframe:
            days_ago = now() - timedelta(days=int(timeframe))
            filters &= Q(timestamp__gte=days_ago)

        # offset calculation
        offset = (page - 1) * items_per_page
        queryset = Content.objects.filter(filters).select_related("author").distinct().order_by("-id")[offset:offset + items_per_page]

        # Pagination
        paginator = Paginator(queryset, items_per_page)
        paged_queryset = paginator.get_page(page)

        serialized = ContentDataSerializer(paged_queryset, many=True)
        # print(serialized.data)

        return Response({
            'results': serialized.data,
            # 'total_pages': paginator.num_pages,
            'total_pages': Content.objects.filter(filters).count(),
            'current_page': page,
        }, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        """
           TODO: This api is very hard to read, and inefficient.
            The users complaining that the contents they are seeing is not being updated.
            Please find out, why the stats are not being updated.
            ------------------
            Things to change:
            1. This api is hard to read, not developer friendly
            2. Support list, make this api accept list of objects and save it
            3. Fix the users complain
        """
        serializer = ContentDataPostSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        # Using bulk creation with validated data for optimization
        serializer.save()
        return Response({"detail": "Content updated successfully"}, status=status.HTTP_200_OK)


class ContentStatsAPIView(APIView):
    """
    TODO: This api is taking way too much time to resolve.
     Contents that will be fetched using `ContentAPIView`, we need stats for that
     So it must have the same filters as `ContentAPIView`
     Filter Support for client side
            - author_id: Author's db id
            - author_username: Author's username
            - timeframe: Content that has timestamp: now - 'x' days
            - tag_id: Tag ID
            - title (insensitive match IE: SQL `ilike %text%`)
     -------------------------
     Things To do:
     1. Make the api performant
     2. Fix the additional data point (IE: total engagement, total engagement rate)
     3. Filter Support for client side
         - author_id: Author's db id
         - author_id: Author's db id
         - author_username: Author's username
         - timeframe: Content that has timestamp: now - 'x' days
         - tag_id: Tag ID
         - title (insensitive match IE: SQL `ilike %text%`)
     --------------------------
     Bonus: What changes do we need if we want timezone support?
    """

    def get(self, request):
        query_params = request.query_params
        filters = Q()

        filter_mappings = {
            'author_id': 'author_id',
            'author_username': 'author__username__iexact',
            'tag_id': 'contenttag__tag_id',
            'title': 'title__icontains'
        }

        # Apply filters dynamically
        for param, db_field in filter_mappings.items():
            value = query_params.get(param, None)
            if value:
                filters &= Q(**{db_field: value})

        # Timeframe filter
        timeframe = query_params.get('timeframe', None)
        if timeframe:
            days_ago = now() - timedelta(days=int(timeframe))
            filters &= Q(timestamp__gte=days_ago)

        # query with engagement, engagement rate calculation
        queryset = Content.objects.filter(filters).aggregate(
            total_likes=Coalesce(Sum('like_count'), 0),
            total_comments=Coalesce(Sum('comment_count'), 0),
            total_shares=Coalesce(Sum('share_count'), 0),
            total_views=Coalesce(Sum('view_count'), 0),
            total_contents=Count('id', distinct=True),
            total_engagement=Coalesce(Sum(F('like_count') + F('comment_count') + F('share_count')), 0),
            total_engagement_rate=Case(
                When(total_views=0, then=0),
                default=F('total_engagement') / F('total_views'),
                output_field=FloatField()
            )
        )

        return Response(queryset, status=status.HTTP_200_OK)




