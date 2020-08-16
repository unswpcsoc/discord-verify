"""Test the iam.verify module."""

import pytest
from time import time
from unittest.mock import patch, AsyncMock, MagicMock
from iam.verify import (
    State, proc_begin, proc_restart
)
from iam.db import MemberKey, MemberNotFound, make_def_member_data
from iam.config import PREFIX, VER_ROLE
import discord

def filter_dict(dict, except_keys):
    return {k:v for k,v in dict.items() if k not in except_keys}

def new_mock_user(id):
    user = AsyncMock()
    user.id = id
    user.typing = MagicMock()
    return user

@pytest.mark.asyncio
async def test_begin_standard():
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

    # Ensure user was sent correct prompt.
    member.send.assert_awaited_with("What is your full name as it appears on "
        "your government-issued ID?\nYou can restart this verification "
        f"process at any time by typing `{PREFIX}restart`.")

    # Ensure user state updated to awaiting name.
    db.update_member_data.assert_called_once_with(member.id,
        {MemberKey.VER_STATE: State.AWAIT_NAME})

@pytest.mark.asyncio
async def test_restart_standard():
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

        # Ensure user entry in database updated accordingly.
        call_args_list = db.update_member_data.call_args_list
        assert len(call_args_list) == 2
        call_args = call_args_list[0].args
        assert call_args[0] == user.id
        assert filter_dict(call_args[1], [MemberKey.VER_TIME]) == \
            {MemberKey.VER_STATE: None}
        assert call_args[1][MemberKey.VER_TIME] >= before_time and \
            call_args[1][MemberKey.VER_TIME] < time()

        # Ensure user was sent correct prompt.
        user.send.assert_awaited_with("What is your full name as it appears "
            "on your government-issued ID?\nYou can restart this verification "
            f"process at any time by typing `{PREFIX}restart`.")

        # Ensure user state updated to awaiting name.
        db.update_member_data.assert_called_with(user.id,
            {MemberKey.VER_STATE: State.AWAIT_NAME})
