from rest_framework.exceptions import ValidationError
from flowback.common.services import get_object, model_update
from flowback.files.services import upload_collection
from flowback.group.services import group_notification, group_schedule
from flowback.notification.services import NotificationManager
from flowback.poll.models import Poll, PollProposal
from flowback.group.selectors import group_user_permissions
from django.utils import timezone
from datetime import datetime

from flowback.poll.services.vote import poll_proposal_vote_count
from flowback.poll.tasks import poll_area_vote_count, poll_prediction_bet_count

poll_notification = NotificationManager(sender_type='poll', possible_categories=['timeline',
                                                                                 'poll',
                                                                                 'comment_self',
                                                                                 'comment_all'])


def poll_notification_subscribe(*, user_id: int, poll_id: int, categories: list[str]):
    poll = get_object(Poll, id=poll_id)
    group_user_permissions(user=user_id, group=poll.created_by.group.id)

    poll_notification.channel_subscribe(user_id=user_id, sender_id=poll.id, category=categories)


def poll_create(*, user_id: int,
                group_id: int,
                title: str,
                description: str,
                start_date: datetime,
                proposal_end_date: datetime = None,
                prediction_statement_end_date: datetime = None,
                area_vote_end_date: datetime = None,
                prediction_bet_end_date: datetime = None,
                delegate_vote_end_date: datetime = None,
                vote_end_date: datetime = None,
                end_date: datetime = None,
                poll_type: int,
                public: bool,
                tag: int,
                pinned: bool,
                dynamic: bool,
                attachments: list = None,
                quorum: int = None
                ) -> Poll:

    group_user = group_user_permissions(user=user_id, group=group_id, permissions=['create_poll', 'admin'])

    if pinned and not group_user.is_admin:
        raise ValidationError('Permission denied')

    if quorum is not None and not group_user.permission.poll_quorum and not group_user.is_admin:
        raise ValidationError("Permission denied for custom poll quorum")

    collection = None
    if attachments:
        collection = upload_collection(user_id=user_id,
                                       file=attachments,
                                       upload_to="group/poll/attachments")

    if poll_type == Poll.PollType.SCHEDULE:
        if not end_date:
            raise ValidationError('Missing required parameter(s) for schedule poll')

        elif not dynamic:
            raise ValidationError('Schedule poll must be dynamic')

    elif not all([proposal_end_date,
                  prediction_statement_end_date,
                  area_vote_end_date,
                  prediction_bet_end_date,
                  delegate_vote_end_date,
                  vote_end_date,
                  end_date]):
        raise ValidationError('Missing required parameter(s) for generic poll')

    poll = Poll(created_by=group_user, title=title, description=description,
                start_date=start_date, proposal_end_date=proposal_end_date,
                prediction_statement_end_date=prediction_statement_end_date, area_vote_end_date=area_vote_end_date,
                prediction_bet_end_date=prediction_bet_end_date, delegate_vote_end_date=delegate_vote_end_date,
                vote_end_date=vote_end_date, end_date=end_date, poll_type=poll_type,
                public=public, tag_id=tag, pinned=pinned, dynamic=dynamic, quorum=quorum,
                attachments=collection)

    poll.full_clean()
    poll.save()

    # Group notification
    group_notification.create(sender_id=group_id, action=poll_notification.Action.update, category='poll',
                              message=f'User {group_user.user.username} created poll {poll.title}',
                              timestamp=start_date, related_id=poll.id)

    poll_area_vote_count.apply_async(kwargs=dict(poll_id=poll.id), eta=poll.area_vote_end_date)
    poll_prediction_bet_count.apply_async(kwarsg=dict(poll_id=poll.id), eta=poll.prediction_bet_end_date)

    # Poll notification
    for date, name, phase in poll.labels:
        poll_notification.create(sender_id=poll.id, action=poll_notification.Action.update, category='timeline',
                                 message=f'Poll {poll.title} has started {phase.replace("_", " ").capitalize()} phase')

    if poll_type == Poll.PollType.SCHEDULE:
        group_notification.create(sender_id=group_id, action=group_notification.Action.update, category='schedule',
                                  message=f'Poll {poll.title} has finished, group schedule has been updated')

    return poll


def poll_update(*, user_id: int, poll_id: int, data) -> Poll:
    poll = get_object(Poll, id=poll_id)
    group_user = group_user_permissions(user=user_id, group=poll.created_by.group.id)

    if data.get('pinned') is not None and not group_user.is_admin:
        raise ValidationError('Permission denied')

    non_side_effect_fields = ['title', 'description', 'pinned']

    poll, has_updated = model_update(instance=poll,
                                     fields=non_side_effect_fields,
                                     data=data)

    return poll


# TODO remove related notifications
def poll_delete(*, user_id: int, poll_id: int) -> None:
    poll = get_object(Poll, id=poll_id)
    group_id = poll.created_by.group.id
    group_user = group_user_permissions(user=user_id, group=group_id)

    force_deletion_access = group_user_permissions(group_user=group_user, permissions=['admin', 'force_delete_poll'],
                                                   raise_exception=False)

    if poll.created_by == group_user and not force_deletion_access:
        if poll.current_phase != 'waiting':
            raise ValidationError("Only administrators can delete ongoing/finished polls")

    else:
        group_user_permissions(group_user=group_user, permissions=['admin', 'force_delete_poll'])

    # Remove future notifications
    if poll.current_phase == 'waiting':
        group_notification.delete(sender_id=group_id, category='poll', related_id=poll.id)

    def delete_notifications_after(phase): poll_notification.delete(sender_id=poll_id,
                                                                    category='timeline',
                                                                    timestamp__gt=phase)
    match poll.current_phase:
        case 'waiting':
            delete_notifications_after(poll.proposal_end_date)
        case 'proposal':
            delete_notifications_after(poll.prediction_statement_end_date)
        case 'area_vote':
            delete_notifications_after(poll.area_vote_end_date)
        case 'prediction_bet':
            delete_notifications_after(poll.prediction_bet_end_date)
        case 'delegate_vote':
            delete_notifications_after(poll.delegate_vote_end_date)
        case 'vote':
            delete_notifications_after(poll.vote_end_date)
        case 'result':
            delete_notifications_after(poll.end_date)

    if poll.attachments:
        poll.attachments.delete()

    poll.delete()


def poll_finish(*, poll_id: int) -> None:
    poll = get_object(Poll, id=poll_id)

    if poll.status:
        raise ValidationError("Poll is already finished")

    poll_proposal_vote_count(poll_id=poll_id)
    poll.result = True
    poll.save()


def poll_refresh(*, poll_id: int) -> None:
    poll = get_object(Poll, id=poll_id)

    if not poll.dynamic:
        raise ValidationError("Attempted to refresh a poll that doesn't allow live update")

    if poll.status:
        raise ValidationError("Attempted to refresh a poll that's already finished")

    poll_proposal_vote_count(poll_id=poll_id)


# TODO setup celery
def poll_refresh_cheap(*, poll_id: int) -> None:
    poll = get_object(Poll, id=poll_id)

    if (poll.dynamic and not poll.status) or (not poll.status and timezone.now() >= poll.end_date):
        poll_proposal_vote_count(poll_id=poll_id)
        poll.refresh_from_db()

        # Add the event if the poll finished
        if poll.poll_type == Poll.PollType.SCHEDULE:
            event = PollProposal.objects.filter(poll=poll).order_by('score')
            if event.exists():
                event = event.first().pollproposaltypeschedule.event
                group_schedule.create_event(schedule_id=poll.created_by.group.schedule_id,
                                            title=poll.title,
                                            start_date=event.start_date,
                                            end_date=event.end_date,
                                            origin_name='poll',
                                            origin_id=poll.id,
                                            description=poll.description)

        poll.save()
