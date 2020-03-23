
__author__ = '(Multiple)'
__project__ = "Food-Pantry-Inventory"
__creation_date__ = "06/03/2019"


from django.core.exceptions import ValidationError
from django.db.models import Count
from django.test import TestCase

from fpiweb.forms import \
    BoxItemForm, \
    BuildPalletForm,\
    ExistingLocationForm, \
    ExistingLocationWithBoxesForm, \
    LocationForm, \
    NewBoxForm
from fpiweb.models import \
    Box, \
    BoxNumber, \
    BoxType, \
    Location, \
    LocRow, \
    LocBin, \
    LocTier, \
    Product


class NewBoxFormTest(TestCase):

    fixtures = ('BoxType', 'Constraints')

    def test_save(self):

        box_type = BoxType.objects.get(box_type_code='Evans')

        post_data = {
            'box_number': '27',
            'box_type': box_type.pk,
        }

        form = NewBoxForm(post_data)
        self.assertTrue(
            form.is_valid(),
            f"{form.errors} {form.non_field_errors()}",
        )
        form.save(commit=True)

        box = form.instance
        self.assertIsNotNone(box)
        self.assertIsNotNone(box.pk)
        self.assertEqual(box_type.box_type_qty, box.quantity)


class BuildPalletFormTest(TestCase):

    def test_is_valid__location_not_specified(self):
        form = BuildPalletForm()
        self.assertFalse(form.is_valid())


class BoxItemFormTest(TestCase):

    fixtures = ('BoxType', 'Product', 'ProductCategory', 'Constraints')

    def test_expire_months(self):
        """ensure that start month <= end month"""
        post_data = {
            'box_number': BoxNumber.format_box_number(12),
            'product': Product.objects.first().pk,
            'exp_year': 2022,
            'exp_month_start': 5,
            'exp_month_end': 3,
        }

        form = BoxItemForm(post_data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            'Exp month end must be later than or equal to Exp month start',
            form.non_field_errors()
        )


class LocationFormTest(TestCase):

    fixtures = ('LocRow', 'LocBin', 'LocTier')

    def test_is_valid__missing_value(self):

        row = LocRow.objects.get(pk=1)

        form = LocationForm({
            'loc_row': row.id,
            'loc_tier': 99,
        })
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {'loc_bin', 'loc_tier'},
            form.errors.keys(),
        )
        self.assertEqual(
            ['This field is required.'],
            form.errors['loc_bin'],
        )
        self.assertEqual(
            ['Select a valid choice. That choice is not one of the available choices.'],
            form.errors['loc_tier'],
        )


class ExistingLocationFormTest(TestCase):

    fixtures = ('LocRow', 'LocBin', 'LocTier', 'Location')

    def test_clean__nonexistent_location(self):

        loc_row = LocRow.objects.get(loc_row='04')
        loc_bin = LocBin.objects.get(loc_bin='03')
        loc_tier = LocTier.objects.get(loc_tier='B2')

        # ----------------------
        # Non-existent location
        # ----------------------
        location = Location.objects.get(
            loc_row=loc_row,
            loc_bin=loc_bin,
            loc_tier=loc_tier,
        )
        location.delete()

        form = ExistingLocationForm({
            'loc_row': loc_row.pk,
            'loc_bin': loc_bin.pk,
            'loc_tier': loc_tier.pk,
        })
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                '__all__': ['Location 04, 03, B2 does not exist.']
            },
            form.errors,
        )
        self.assertEqual(
            ['Location 04, 03, B2 does not exist.'],
            form.non_field_errors(),
        )

    def test_clean__multiple_locations_found(self):

        # -------------------------
        # Multiple locations found
        # -------------------------
        location = Location.objects.get(
            loc_row__loc_row='04',
            loc_bin__loc_bin='04',
            loc_tier__loc_tier='B1'
        )

        # Create a duplicate location
        Location.objects.create(
            loc_row=location.loc_row,
            loc_bin=location.loc_bin,
            loc_tier=location.loc_tier
        )

        form = ExistingLocationForm({
            'loc_row': location.loc_row.pk,
            'loc_bin': location.loc_bin.pk,
            'loc_tier': location.loc_tier.pk,
        })
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                '__all__': ['Multiple 04, 04, B1 locations found'],
            },
            form.errors,
        )
        self.assertEqual(
            ['Multiple 04, 04, B1 locations found'],
            form.non_field_errors(),
        )

    def test_clean__successful_run(self):

        location = Location.objects.get(
            loc_row__loc_row='04',
            loc_bin__loc_bin='02',
            loc_tier__loc_tier='B1',
        )

        form = ExistingLocationForm({
            'loc_row': location.loc_row.pk,
            'loc_bin': location.loc_bin.pk,
            'loc_tier': location.loc_tier.pk,
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(location.pk, form.cleaned_data['location'].pk)


class ExistingLocationWithBoxesFormTest(TestCase):

    fixtures = ('BoxType', 'LocRow', 'LocBin', 'LocTier', 'Location')

    def test_clean(self):

        # ----------------------------------------------------------------
        # super class's clean detects error (i.e. location doesn't exist)
        # ----------------------------------------------------------------
        loc_row = '03'
        loc_bin = '03'
        loc_tier = 'A1'

        location = Location.objects.get(
            loc_row__loc_row=loc_row,
            loc_bin__loc_bin=loc_bin,
            loc_tier__loc_tier=loc_tier,
        )
        location.delete()

        form = ExistingLocationWithBoxesForm({
            'loc_row': location.loc_row,
            'loc_bin': location.loc_bin,
            'loc_tier': location.loc_tier
        })

        self.assertFalse(form.is_valid())
        self.assertEqual(
            {'__all__': ['Location 03, 03, A1 does not exist.']},
            form.errors,
        )
        self.assertEqual(
            ['Location 03, 03, A1 does not exist.'],
            form.non_field_errors(),
        )

        # ---------------------------
        # Try a location w/out boxes
        # ---------------------------

        location = Location.objects.annotate(
            box_count=Count('box')
        ).filter(
            box_count=0
        ).first()

        form = ExistingLocationWithBoxesForm({
            'loc_row': location.loc_row,
            'loc_bin': location.loc_bin,
            'loc_tier': location.loc_tier,
        })

        self.assertFalse(form.is_valid())
        expected_error = "Location {}, {}, {} doesn't have any boxes".format(
            location.loc_row.loc_row,
            location.loc_bin.loc_bin,
            location.loc_tier.loc_tier,
        )
        self.assertEqual(
            {'__all__': [expected_error]},
            form.errors,
        )
        self.assertEqual(
            [expected_error],
            form.non_field_errors(),
        )

        # ---------------------------------------------
        # Add a box to the location form will validate
        # ---------------------------------------------

        Box.objects.create(
            box_type=Box.box_type_default(),
            box_number=BoxNumber.format_box_number(111),
            location=location,
        )

        form = ExistingLocationWithBoxesForm({
            'loc_row': location.loc_row,
            'loc_bin': location.loc_bin,
            'loc_tier': location.loc_tier,
        })

        self.assertTrue(form.is_valid())


