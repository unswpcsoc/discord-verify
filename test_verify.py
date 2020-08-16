"""Test the iam.verify module."""

import pytest
from time import time
from unittest.mock import patch, AsyncMock, MagicMock
from iam.verify import (
    State, proc_begin, proc_restart, state_await_name
)
from iam.db import MemberKey, MemberNotFound, make_def_member_data
from iam.config import PREFIX, VER_ROLE
import discord

def filter_dict(dict, except_keys):
    return {k:v for k,v in dict.items() if k not in except_keys}

def new_mock_user(id):
    user = AsyncMock()
    user.id = id
    user.mention = f"@User_{user.id}#0000"
    user.typing = MagicMock()
    return user

def new_mock_channel(id):
    channel = AsyncMock()
    channel.id = id
    return channel

def new_mock_role(id):
    role = AsyncMock()
    role.id = id
    return role

@pytest.mark.asyncio
async def test_proc_begin_standard():
    """User not undergoing verification can begin verification."""
    # Setup
    db = MagicMock()
    member = new_mock_user(0)
    db.get_member_data = MagicMock(side_effect=MemberNotFound(member.id, ""))
    before_time = time()

    # Call
    await proc_begin(db, None, None, member)

    # Ensure user entry in DB initialised with default data.
    db.set_member_data.assert_called_once()
    call_args = db.set_member_data.call_args.args
    assert call_args[0] == member.id
    assert filter_dict(call_args[1], [MemberKey.VER_TIME]) == \
        filter_dict(make_def_member_data(), [MemberKey.VER_TIME])
    assert call_args[1][MemberKey.VER_TIME] >= before_time and \
        call_args[1][MemberKey.VER_TIME] <= time()

    # Ensure user was sent prompt.
    member.send.assert_awaited_once_with("What is your full name as it "
        "appears on your government-issued ID?\nYou can restart this "
        f"verification process at any time by typing `{PREFIX}restart`.")

    # Ensure user state updated to awaiting name.
    db.update_member_data.assert_called_once_with(member.id,
        {MemberKey.VER_STATE: State.AWAIT_NAME})

    # Ensure no side effects occurred.
    member.add_roles.assert_not_called()

@pytest.mark.asyncio
async def test_proc_begin_already_verifying():
    """User already undergoing verification sent error."""
    for state in State:
        # Setup
        db = MagicMock()
        member = new_mock_user(0)
        member_data = make_def_member_data()
        member_data[MemberKey.VER_STATE] = state
        db.get_member_data.return_value = member_data

        # Call
        await proc_begin(db, None, None, member)

        # Ensure correct user queried.
        db.get_member_data.assert_called_once_with(member.id)

        # Ensure user was sent error.
        member.send.assert_awaited_once_with("You are already undergoing the "
            f"verification process. To restart, type `{PREFIX}restart`.")

        # Ensure no side effects occurred.
        member.add_roles.assert_not_called()
        db.set_member_data.assert_not_called()
        db.update_member_data.assert_not_called()

@pytest.mark.asyncio
async def test_proc_begin_already_verified():
    """User previously verified granted rank immediately."""
    for state in State:
        # Setup
        db = MagicMock()
        member = new_mock_user(0)
        ver_role = new_mock_role(1)
        admin_channel = new_mock_channel(2)
        member_data = make_def_member_data()
        member_data[MemberKey.ID_VER] = True
        member_data[MemberKey.VER_STATE] = state
        db.get_member_data.return_value = member_data

        # Call
        await proc_begin(db, ver_role, admin_channel, member)

        # Ensure correct user queried.
        db.get_member_data.assert_called_once_with(member.id)

        # Ensure user was granted rank.
        member.add_roles.assert_awaited_once_with(ver_role)

        # Ensure user was sent confirmation.
        member.send.assert_awaited_once_with("Our records show you were "
            "verified in the past. You have been granted the rank once again. "
            "Welcome back to the server!")

        # Ensure admin channel was sent confirmation.
        admin_channel.send.assert_awaited_once_with(f"{member.mention} was "
            "previously verified, and has been given the verified rank again "
            "through request.")

        # Ensure no side effects occurred.
        db.set_member_data.assert_not_called()
        db.update_member_data.assert_not_called()

@pytest.mark.asyncio
async def test_proc_restart_standard():
    """User undergoing verification can restart verification."""
    for state in State:
        # Setup
        db = MagicMock()
        user = new_mock_user(0)
        member_data = make_def_member_data()
        member_data[MemberKey.VER_STATE] = state
        db.get_member_data.return_value = member_data
        before_time = time()

        # Call
        await proc_restart(db, user)

        # Ensure correct user queried.
        db.get_member_data.assert_called_once_with(user.id)

        # Ensure user entry in database updated correctly.
        call_args_list = db.update_member_data.call_args_list
        assert len(call_args_list) == 2
        call_args = call_args_list[0].args
        assert call_args[0] == user.id
        assert filter_dict(call_args[1], [MemberKey.VER_TIME]) == \
            {MemberKey.VER_STATE: None}
        assert call_args[1][MemberKey.VER_TIME] >= before_time and \
            call_args[1][MemberKey.VER_TIME] < time()

        # Ensure user was sent prompt.
        user.send.assert_awaited_once_with("What is your full name as it "
            "appears on your government-issued ID?\nYou can restart this "
            f"verification process at any time by typing `{PREFIX}restart`.")

        # Ensure user state updated to awaiting name.
        db.update_member_data.assert_called_with(user.id,
            {MemberKey.VER_STATE: State.AWAIT_NAME})

        # Ensure no side effects occurred.
        user.add_roles.assert_not_called()
        db.set_member_data.assert_not_called()

@pytest.mark.asyncio
async def test_proc_restart_never_verifying():
    """User never started verification sent error."""
    # Setup
    db = MagicMock()
    user = new_mock_user(0)
    db.get_member_data = MagicMock(side_effect=MemberNotFound(user.id, ""))

    # Call
    await proc_restart(db, user)

    # Ensure correct user queried.
    db.get_member_data.assert_called_once_with(user.id)

    # Ensure user was sent error.
    user.send.assert_awaited_once_with("You are not currently being verified.")

    # Ensure no side effects occurred.
    user.add_roles.assert_not_called()
    db.set_member_data.assert_not_called()
    db.update_member_data.assert_not_called()

@pytest.mark.asyncio
async def test_proc_restart_not_verifying():
    """User not undergoing verification sent error."""
    # Setup
    db = MagicMock()
    user = new_mock_user(0)
    db.get_member_data.return_value = make_def_member_data()

    # Call
    await proc_restart(db, user)

    # Ensure correct user queried.
    db.get_member_data.assert_called_once_with(user.id)

    # Ensure user was sent error.
    user.send.assert_awaited_once_with("You are not currently being verified.")

    # Ensure no side effects occurred.
    user.add_roles.assert_not_called()
    db.set_member_data.assert_not_called()
    db.update_member_data.assert_not_called()

@pytest.mark.asyncio
async def test_proc_restart_already_verified():
    """User already verified sent error."""
    for state in State:
        # Setup
        db = MagicMock()
        user = new_mock_user(0)
        member_data = make_def_member_data()
        member_data[MemberKey.ID_VER] = True
        member_data[MemberKey.VER_STATE] = state
        db.get_member_data.return_value = member_data

        # Call
        await proc_restart(db, user)

        # Ensure correct user queried.
        db.get_member_data.assert_called_once_with(user.id)

        # Ensure user was sent error.
        user.send.assert_awaited_once_with("You are already verified.")

        # Ensure no side effects occurred.
        user.add_roles.assert_not_called()
        db.set_member_data.assert_not_called()
        db.update_member_data.assert_not_called()

@pytest.mark.asyncio
async def test_state_await_name_standard():
    """User sending valid name should move on to UNSW student question."""
    # Setup
    db = MagicMock()
    member = new_mock_user(0)
    full_name = "Test User 0"

    # Call
    await state_await_name(db, member, full_name)

    # Ensure user entry in database updated correctly.
    call_args_list = db.update_member_data.call_args_list
    assert len(call_args_list) == 2
    call_args = call_args_list[0].args
    assert call_args == (member.id, {MemberKey.NAME: full_name})

    # Ensure user was sent prompt.
    member.send.assert_awaited_once_with("Are you a UNSW student? Please type "
        "`y` or `n`.")

    # Ensure user state updated to awaiting is UNSW.
    call_args = call_args_list[1].args
    assert call_args == (member.id, {MemberKey.VER_STATE: State.AWAIT_UNSW})

    # Ensure no side effects occurred.
    member.add_roles.assert_not_called()
    db.set_member_data.assert_not_called()

@pytest.mark.asyncio
async def test_state_await_name_too_long():
    """User sending name that is too long sent error."""
    # Setup
    db = MagicMock()
    member = new_mock_user(0)
    full_name = "a" * 501

    # Call
    await state_await_name(db, member, full_name)

    # Ensure user was sent error.
    member.send.assert_awaited_once_with(f"Name must be 500 characters or "
        "fewer. Please try again.")

    # Ensure no side effects occurred.
    member.add_roles.assert_not_called()
    db.set_member_data.assert_not_called()
    db.update_member_data.assert_not_called()
