from django.db import migrations, models

from forum.text import render_markdown, summarize


def render_bodies(apps, schema_editor):
    for name in ("Post", "Comment"):
        model = apps.get_model("forum", name)
        items = list(model.objects.only("pk", "body"))
        for item in items:
            item.body_html = render_markdown(item.body)
            item.excerpt = summarize(item.body_html)
        model.objects.bulk_update(items, ["body_html", "excerpt"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("forum", "0003_access_intervals")]
    operations = [
        migrations.AddField("post", "body_html", models.TextField(default="", editable=False)),
        migrations.AddField("post", "excerpt", models.CharField(default="", editable=False, max_length=200)),
        migrations.AddField("comment", "body_html", models.TextField(default="", editable=False)),
        migrations.AddField("comment", "excerpt", models.CharField(default="", editable=False, max_length=200)),
        migrations.RunPython(render_bodies, migrations.RunPython.noop),
    ]
