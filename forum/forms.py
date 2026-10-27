from django import forms

from accounts.models import SchoolTier

from .models import AccessMode, Comment, Post


class PostForm(forms.ModelForm):
    body = forms.CharField(label="内容", max_length=20000, widget=forms.Textarea(attrs={"rows": 14, "placeholder": "说说你的问题、观察或想法。具体的背景，往往能带来更好的回答。", "data-editor": ""}))

    class Meta:
        model = Post
        fields = ("kind", "topic", "title", "body", "access_mode", "read_min_tier", "read_max_tier", "reply_min_tier", "reply_max_tier")
        labels = {"topic": "话题"}
        widgets = {
            "kind": forms.RadioSelect,
            "topic": forms.Select(attrs={"class": "topic-select"}),
            "title": forms.TextInput(attrs={"placeholder": "一个具体、清楚的标题", "autofocus": True, "class": "title-input"}),
            "access_mode": forms.RadioSelect,
            **{field: forms.HiddenInput for field in ("read_min_tier", "read_max_tier", "reply_min_tier", "reply_max_tier")},
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topic"].empty_label = "选择一个话题"
        self.user = user
        self.tiers = list(SchoolTier.objects.all())
        self.own_ranks = sorted(user.school_tier_ranks)

    def clean(self):
        data = super().clean()
        if data.get("access_mode") != AccessMode.RANGE:
            for scope in ("read", "reply"):
                data[f"{scope}_min_tier"] = data[f"{scope}_max_tier"] = None
            return data
        for scope, label in (("read", "阅读"), ("reply", "回复")):
            low, high = data.get(f"{scope}_min_tier"), data.get(f"{scope}_max_tier")
            if low is None or high is None or low.pk > high.pk:
                raise forms.ValidationError(f"请选择有效的{label}等级区间。")
            if not any(low.pk <= rank <= high.pk for rank in self.own_ranks):
                raise forms.ValidationError(f"{label}区间必须包含你任意一份已绑定学历的学校等级。")
        if not (data["read_min_tier"].pk <= data["reply_min_tier"].pk <= data["reply_max_tier"].pk <= data["read_max_tier"].pk):
            raise forms.ValidationError("回复区间必须包含在阅读区间内。")
        return data


class CommentForm(forms.ModelForm):
    body = forms.CharField(label="回复", max_length=10000, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "分享你的经验，或接着这个问题一起想一想。"}))

    class Meta:
        model = Comment
        fields = ("body", "parent")
        widgets = {"parent": forms.HiddenInput}

    def __init__(self, *args, post, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parent"].queryset = Comment.objects.filter(post=post, is_deleted=False)


class VoteForm(forms.Form):
    value = forms.ChoiceField(choices=[("1", "赞同"), ("-1", "不赞同")])
