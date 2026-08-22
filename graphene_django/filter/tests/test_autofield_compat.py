"""Regression tests: auto-field primary keys must resolve to GlobalIDFilter.

Django 6.0 refactored ``BigAutoField`` and ``SmallAutoField`` so that they no
longer inherit from ``AutoField`` (they now combine ``AutoFieldMixin`` with a
concrete integer field). django-filter resolves filter classes by walking the
field class's MRO with exact dict-key lookups (``try_dbfield``), so an override
registered only for ``AutoField`` is silently skipped on Django 6+ and the pk
falls through to ``NumberFilter`` via ``IntegerField``/``BigIntegerField``.

These tests pin the resolution of *all three* auto-field pk types to
``GlobalIDFilter``, independent of the Django version and independent of what
``DEFAULT_AUTO_FIELD`` resolves to for any given model.
"""

import pytest

from graphene_django.utils import DJANGO_FILTER_INSTALLED

pytestmark = []

if DJANGO_FILTER_INSTALLED:
    from django.db import models
    from django_filters.utils import try_dbfield

    from graphene_django.filter.filters import GlobalIDFilter
    from graphene_django.filter.filterset import (
        GrapheneFilterSetMixin,
        custom_filterset_factory,
    )
    from graphene_django.forms import GlobalIDFormField

    # All three exist in every supported Django version (>= 3.2).
    AUTO_FIELD_CLASSES = [
        models.AutoField,
        models.BigAutoField,
        models.SmallAutoField,
    ]

    AUTO_FIELD_IDS = ["auto", "big_auto", "small_auto"]

    def make_pk_model(field_class):
        """Create a registered test model with the given auto-field pk type.

        One unique model name per field class; each is only created once per
        session because the ``try_dbfield`` test below never instantiates
        models. The models are never queried or migrated; only
        ``model._meta`` and filter resolution are exercised.
        """
        model_name = f"AutoPkCompat{field_class.__name__}"
        return type(
            model_name,
            (models.Model,),
            {
                "__module__": __name__,
                "name": models.CharField(max_length=30),
                "id": field_class(primary_key=True),
                "Meta": type("Meta", (), {"app_label": "tests"}),
            },
        )

    @pytest.mark.parametrize("field_class", AUTO_FIELD_CLASSES, ids=AUTO_FIELD_IDS)
    def test_auto_field_pk_overrides_resolve_global_id_filter(field_class):
        """The override map itself must answer for every auto-field type.

        Mirrors django-filter's actual resolution path:
        ``try_dbfield(FILTER_DEFAULTS.get, field.__class__)`` walks the
        field's MRO looking up exact dict keys.
        """
        resolved = try_dbfield(GrapheneFilterSetMixin.FILTER_DEFAULTS.get, field_class)
        assert resolved is not None, (
            f"{field_class.__name__} has no entry reachable via its MRO"
        )
        assert resolved["filter_class"] is GlobalIDFilter

    @pytest.mark.parametrize("field_class", AUTO_FIELD_CLASSES, ids=AUTO_FIELD_IDS)
    def test_filterset_for_model_with_auto_pk_uses_global_id_filter(field_class):
        """End-to-end: a FilterSet built over a model whose explicit pk is
        each auto-field type must expose a GlobalIDFilter for "id"."""

        model = make_pk_model(field_class)

        filterset = custom_filterset_factory(model, fields=["id"])
        id_filter = filterset.base_filters["id"]
        assert isinstance(id_filter, GlobalIDFilter)
        assert id_filter.field_class == GlobalIDFormField
else:
    pytestmark.append(
        pytest.mark.skipif(
            True, reason="django_filters not installed or not compatible"
        )
    )
