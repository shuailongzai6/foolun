from django.db import migrations


def create_topics(apps, schema_editor):
    Topic = apps.get_model("forum", "Topic")
    topics = [
        ("life", "校园生活", "把日常过成值得分享的片段", "coffee", "yellow"),
        ("academic", "学习与科研", "认真提问，一起把问题想明白", "book", "green"),
        ("career", "实习与未来", "选一条属于自己的路", "briefcase", "blue"),
        ("tech", "科技与工具", "聊聊让学习和生活更有趣的工具", "cpu", "purple"),
        ("thoughts", "想法与共鸣", "小小的思考，也值得被听见", "sparkles", "rose"),
    ]
    for position, (slug, name, description, icon, color) in enumerate(topics):
        Topic.objects.get_or_create(slug=slug, defaults={
            "name": name, "description": description, "icon": icon, "color": color, "position": position,
        })


class Migration(migrations.Migration):
    dependencies = [("forum", "0001_initial")]
    operations = [migrations.RunPython(create_topics, migrations.RunPython.noop)]
