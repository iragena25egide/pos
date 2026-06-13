from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailAuthBackend(ModelBackend):
    """
    Custom authentication backend to allow users to log in using either their username or email address.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Check if the user exists by either username or email
            user = User.objects.get(Q(username__iexact=username) | Q(email__iexact=username))
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            # If multiple users have the same email, get the first one
            user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
