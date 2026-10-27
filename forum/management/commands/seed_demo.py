from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Education, School, SchoolTier, User
from forum.models import Comment, Notification, Post, PostVote, AccessMode, Topic, TopicFollow


class Command(BaseCommand):
    help = "生成可重复运行的开发演示数据；仅在 DEBUG=1 时可用。"

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("演示数据只能用于开发环境。")
        now = timezone.now()
        profiles = [
            ("demo", "林夏", "浙江大学", "浙大", "student", "在课程与生活之间，寻找一点新鲜的可能。"),
            ("demo_zhixia", "知夏", "复旦大学", "复旦", "student", "喜欢校园里的秋天，也喜欢没有标准答案的问题。"),
            ("demo_zhou", "周行", "北京大学", "北大", "alumni", "毕业以后，仍然觉得认真提问是一种重要的能力。"),
            ("demo_yifan", "亦凡", "南京大学", "南大", "student", "在实验室与图书馆之间走走停停。"),
            ("demo_chen", "陈澄", "浙江大学", "浙大", "student", "分享一点学习经验，记录一点日常观察。"),
            ("demo_luyao", "路遥", "上海交通大学", "交大", "alumni", "工作了几年，还在学习如何选一条适合自己的路。"),
        ]
        if User.objects.filter(username__in=[item[0] for item in profiles], is_demo=False).exists():
            raise CommandError("演示用户名已被真实账户使用，未生成任何数据。")
        people = []
        for username, name, school_name, label, status, bio in profiles:
            school, _ = School.objects.get_or_create(name=school_name, defaults={"short_name": label})
            user, created = User.objects.get_or_create(username=username, defaults={
                "display_name": name, "bio": bio, "is_demo": True,
            })
            if created:
                user.set_password("Tongchuang2026!")
                user.save(update_fields=["password"])
            Education.objects.get_or_create(user=user, school=school, is_demo=True, defaults={
                "status": status, "education_level": "本科", "major": "示例专业",
                "enrollment_year": 2023 if status == "student" else 2017,
                "graduation_year": 2021 if status == "alumni" else None,
                "expected_graduation_year": 2027 if status == "student" else None,
            })
            people.append(user)
        topics = {topic.slug: topic for topic in Topic.objects.all()}
        entries = [
            (0, "academic", "question", "读大学这几年，哪门课真正改变了你的思考方式？", "不是最容易拿高分的那门，也不一定和专业直接相关。\n\n对我来说，是一门通识课。老师反复问我们：**这个判断的依据是什么？有没有另一种解释？**\n\n后来发现，这两个问题在写论文、做项目，甚至日常交流里都很好用。\n\n想听听大家的经历：是哪门课、哪位老师，或课堂上的哪一刻，让你开始换一种方式看问题？"),
            (1, "life", "discussion", "校园里的秋天，有哪些不必赶路的地方？", "昨天从图书馆出来，临时决定绕远一点。\n\n走到那条平时只当作捷径的小路，才发现树叶已经变了颜色。没有赶下一节课，也没有一边走一边看手机，突然觉得校园变大了。\n\n最近在尝试给自己留一点没有任务的散步时间。你们学校有没有这样的地方？一条小路、一片草地，或一个可以坐很久的长椅。\n\n> 偶尔停下来，也是一种抵达。"),
            (5, "career", "question", "第一次实习：选大平台，还是能真正做事的小团队？", "最近在帮学弟看两个实习机会。一个平台知名度高，但工作内容比较固定；另一个团队很小，却可以跟着完整的项目走一遍。\n\n刚毕业时，我也很看重公司名字。现在再回头看，真正帮助我进入下一段工作的，是当时做过哪些事、怎么做的，以及谁愿意认真给反馈。\n\n想听听在校同学和校友的看法：**如果只能选一个，你会怎么判断？**有哪些面试时就值得问清楚的问题？"),
            (3, "academic", "question", "研究生选导师，除了论文数量，还应该看哪些信号？", "最近开始联系导师，发现资料页能看到的信息和实际科研体验之间，还有很大距离。\n\n整理了几个想问的问题：\n\n- 组会是讨论问题，还是主要汇报进度？\n- 学生能否选择或调整课题？\n- 遇到实验失败，通常如何一起分析？\n- 毕业生去了哪里，对这段经历怎么看？\n\n如果大家经历过这个阶段，有哪些后来才意识到重要、却容易在申请时忽略的信号？"),
            (4, "tech", "discussion", "把 AI 当学习搭子之后，我开始重新练习提问", "一开始总想让它直接给答案。后来发现，自己看懂了一段解释，不代表真的会做。\n\n现在更常用的方式，是让它先问我几个问题，检查我已经理解了哪一步，再补上缺的部分。\n\n我给自己的小规则是：\n\n1. 先用自己的话描述问题。\n2. 在看到答案前，写下一版自己的推理。\n3. 最后离开对话，独立复述一遍。\n\n工具没有替我理解，但让我更清楚自己哪里还没理解。大家有什么好用的学习方法？"),
            (2, "thoughts", "discussion", "有没有一件小事，让你觉得自己在大学里慢慢长大了？", "不是很大的成就，可能只是一个以前做不到的小决定。\n\n对我来说，是第一次没有因为别人都报名，就跟着参加一项活动。认真想了想自己当时的精力，然后好好地说了不。\n\n后来发现，**知道什么值得做，和知道什么可以不做，是一样重要的。**\n\n校园生活好像总有很多可以被量化的成绩。也想给那些很小、很慢，却确实发生了的变化留一点位置。"),
            (1, "life", "discussion", "每周留一个没有安排的下午，反而让我更有余裕", "原本以为一个空下午会浪费掉，实际试了几周，发现它成了生活的缓冲。\n\n可以整理前几天没消化的笔记，也可以去运动，或者只是和朋友慢慢吃一顿饭。没有安排，并不等于什么都不做，只是不用提前把自己塞满。\n\n最近课业比较重的同学，有什么让自己保持节奏的小习惯？"),
            (0, "academic", "discussion", "给学弟学妹：一份不会把人塞满的选课建议", "选课之前，先看一眼自己一周真实可用的时间。\n\n**不是只看学分，更要看课程之间怎样搭配。**实验课、小组项目和需要大量阅读的通识课，如果全放在同一学期，常常比课表看起来更忙。\n\n我现在的做法是，留一门单纯因为好奇而选的课，再留一点不被课表占满的时间。\n\n选课是一种取舍，也是一种认识自己的练习。"),
            (5, "career", "discussion", "毕业三年之后，我依然会回学校走一走", "最近回校园参加了一次分享。比起讲自己做成了什么，更想聊当时有哪些判断后来变了。\n\n走出学校之后，发现一条路很少是一直直着走的。可以调整，可以重新学习，也可以暂时不知道答案。\n\n如果有一句话想告诉当时的自己，大概是：不用把每一步都走成最终决定。"),
            (4, "life", "question", "浙大同学来聊聊：紫金港有哪些安静的自习角落？", "想收集一点图书馆之外的自习地点。\n\n最好能安静阅读，也可以偶尔和同学小声讨论。是否有插座、开放到几点，也很有帮助。\n\n这篇仅向同校同学开放阅读和回复，方便大家分享具体的位置与体验。"),
        ]
        posts = []
        for index, (person, topic_slug, kind, title, body) in enumerate(entries):
            post, created = Post.objects.get_or_create(author=people[person], title=title, defaults={
                "topic": topics[topic_slug], "kind": kind, "body": body,
                "created_at": now - timedelta(hours=index * 3 + 1),
            })
            if created:
                for voter in people[: max(2, 6 - index % 4)]:
                    PostVote.objects.create(user=voter, post=post, value=1)
            posts.append(post)
        posts[-1].access_mode = AccessMode.CAMPUS
        posts[-1].save(update_fields=["access_mode"])
        comments = [
            (0, 2, "对我来说是科学哲学。最有价值的不是记住某个结论，而是学会区分：哪些是观察，哪些是解释，哪些还只是猜想。"),
            (0, 1, "一门写作课。老师让我们每次都删掉自己最舍不得、但其实没有帮助表达的那句话，后来做汇报也一直在用这个习惯。"),
            (0, 3, "概率论。认识到很多判断都带着不确定性以后，反而没有那么急着对每件事下结论了。"),
            (1, 0, "我们学校的一片小草地，路过的人很多，真正坐下来的人却不多。傍晚去会很舒服。"),
            (2, 2, "我会优先问：这个岗位由谁带、怎样给反馈、上一位实习生具体做过什么。这些答案通常比团队规模更有参考价值。"),
            (3, 5, "如果能联系到已经毕业的学生，可以请他们讲一个遇到困难时导师如何处理的具体例子。具体故事比概括性的评价更有信息量。"),
            (4, 3, "很赞同最后一步。关掉对话之后，拿一张白纸重新说明一遍，比继续问十个问题更能发现盲点。"),
            (5, 1, "第一次认真给自己做一顿饭。发现照顾好自己，并不是等忙完以后才做的事。"),
            (9, 0, "东区有几处靠窗的位置，平时午后人不多。大家去之前也可以看看当天的开放安排。"),
        ]
        for post_index, person_index, body in comments:
            comment, created = Comment.objects.get_or_create(post=posts[post_index], author=people[person_index], body=body)
            if created and comment.post.author_id != comment.author_id:
                Notification.objects.create(recipient=comment.post.author, actor=comment.author, post=comment.post, comment=comment)
        for item in (topics["academic"], topics["life"], topics["tech"]):
            TopicFollow.objects.get_or_create(user=people[0], topic=item)
        Post.objects.get_or_create(author=people[0], title="区间讨论示例：阅读与回复可以不同", defaults={
            "topic": topics["thoughts"],
            "body": "这篇向 211 非 985 至华五学校开放阅读，回复只开放给华五。\n\n只要任意一份已绑定学历符合即可。首页偏好可能隐藏这篇，但不会改变直达链接的访问权限。",
            "access_mode": AccessMode.RANGE,
            "read_min_tier": SchoolTier.objects.get(rank=40), "read_max_tier": SchoolTier.objects.get(rank=60),
            "reply_min_tier": SchoolTier.objects.get(rank=60), "reply_max_tier": SchoolTier.objects.get(rank=60),
        })
        self.stdout.write(self.style.SUCCESS("演示数据已准备好。开发登录：demo / Tongchuang2026!"))
