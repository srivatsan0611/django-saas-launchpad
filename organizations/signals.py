from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Organization, Membership


@receiver(post_save, sender=Organization)
def create_owner_membership(sender, instance, created, **kwargs):
    """
    Automatically create an owner membership for the organization creator.

    When a new organization is created, this signal handler ensures that
    the user who created it (the owner) is automatically added as a member
    with the 'owner' role.

    Args:
        sender: The model class (Organization)
        instance: The actual Organization instance being saved
        created: Boolean indicating if this is a new record
        **kwargs: Additional keyword arguments from the signal
    """
    if created:
        # Create owner membership for the user who created the organization
        Membership.objects.create(
            user=instance.owner,
            organization=instance,
            role='owner'
        )
