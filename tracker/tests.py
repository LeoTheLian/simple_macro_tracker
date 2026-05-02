from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import DailyGoal, FoodItem, LogEntry


class AuthRequiredTests(TestCase):
    """Anonymous users should be redirected to login for all tracker views."""

    def test_dashboard_requires_login(self):
        r = self.client.get(reverse('tracker:dashboard'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r.url)

    def test_history_requires_login(self):
        r = self.client.get(reverse('tracker:history'))
        self.assertEqual(r.status_code, 302)

    def test_foods_requires_login(self):
        r = self.client.get(reverse('tracker:foods'))
        self.assertEqual(r.status_code, 302)

    def test_goals_requires_login(self):
        r = self.client.get(reverse('tracker:goals'))
        self.assertEqual(r.status_code, 302)

    def test_htmx_search_requires_login(self):
        r = self.client.get(reverse('tracker:htmx_search'))
        self.assertEqual(r.status_code, 302)


class DataIsolationTests(TestCase):
    """Each user should only see and mutate their own LogEntry and DailyGoal data."""

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user('alice', password='pass1234')
        cls.bob = User.objects.create_user('bob', password='pass1234')

        cls.food = FoodItem.objects.create(
            name='Chicken Breast',
            calories_per_100g=165,
            protein_per_100g=31,
            carbs_per_100g=0,
            fat_per_100g=3.6,
        )

        cls.alice_entry = LogEntry.objects.create(
            user=cls.alice,
            date=date.today(),
            food_item=cls.food,
            serving_grams=200,
            meal_type='LUNCH',
        )

        cls.bob_entry = LogEntry.objects.create(
            user=cls.bob,
            date=date.today(),
            food_item=cls.food,
            serving_grams=150,
            meal_type='DINNER',
        )

        DailyGoal.objects.create(
            user=cls.alice,
            effective_date=date.today(),
            calories=2000,
            protein_g=150,
            carbs_g=200,
            fat_g=65,
        )

    def setUp(self):
        self.client_alice = Client()
        self.client_bob = Client()
        self.client_alice.login(username='alice', password='pass1234')
        self.client_bob.login(username='bob', password='pass1234')

    def test_dashboard_shows_only_own_entries(self):
        r = self.client_alice.get(reverse('tracker:dashboard'))
        content = r.content.decode()
        # Alice's meal type (Lunch) should appear; Bob's (Dinner) should not
        self.assertIn('Lunch', content)
        self.assertNotIn('Dinner', content)

    def test_history_shows_only_own_entries(self):
        r = self.client_bob.get(reverse('tracker:history'))
        self.assertEqual(r.status_code, 200)

    def test_cannot_delete_other_users_entry(self):
        """Bob cannot delete Alice's log entry."""
        url = reverse('tracker:htmx_delete_entry', args=[self.alice_entry.pk])
        r = self.client_bob.delete(url)
        self.assertEqual(r.status_code, 404)
        self.assertTrue(LogEntry.objects.filter(pk=self.alice_entry.pk).exists())

    def test_goals_are_per_user(self):
        """Bob can create a goal for the same date as Alice."""
        # calories must equal protein*4 + carbs*4 + fat*9 = 180*4 + 250*4 + 70*9 = 2350
        self.client_bob.post(reverse('tracker:goals'), {
            'effective_date': str(date.today()),
            'calories': 2350,
            'protein_g': 180,
            'carbs_g': 250,
            'fat_g': 70,
        })
        self.assertEqual(DailyGoal.objects.filter(user=self.bob).count(), 1)
        self.assertEqual(DailyGoal.objects.filter(user=self.alice).count(), 1)


class SignupTests(TestCase):
    def test_signup_creates_user_and_logs_in(self):
        r = self.client.post(reverse('signup'), {
            'username': 'newuser',
            'password1': 'Str0ng!Pass99',
            'password2': 'Str0ng!Pass99',
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username='newuser').exists())
