import json
from pathlib import Path

from django.db import migrations


def seed_catalogue(apps, schema_editor):
    Tier = apps.get_model("accounts", "SchoolTier")
    School = apps.get_model("accounts", "School")
    names = ["专科", "普通本科", "双一流非211", "211非985", "其他985", "华五", "TOP2"]
    for rank, name in enumerate(names, start=1):
        Tier.objects.get_or_create(rank=rank * 10, defaults={"name": name})
    source = Path(__file__).resolve().parents[1] / "data" / "schools-v1.json"
    schools = json.loads(source.read_text(encoding="utf-8"))
    School.objects.bulk_create([School(name=name, tier_id=rank) for name, rank in schools.items()], ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_multiple_educations")]
    operations = [migrations.RunPython(seed_catalogue, migrations.RunPython.noop)]
