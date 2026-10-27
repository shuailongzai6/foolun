from django.core.management.base import BaseCommand

from forum.models import Comment, Post


class Command(BaseCommand):
    help = "按当前 Markdown 规则重新生成帖子和回复的 HTML 与摘要。"

    def handle(self, *args, **options):
        for model in (Post, Comment):
            for item in model.objects.only("pk", "body").iterator():
                item.save(update_fields=["body"])
        self.stdout.write(self.style.SUCCESS("已重新渲染全部帖子和回复。"))
