"""MIT License

Copyright (c) 2020 Computer Enthusiasts Society

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

"""Handle database functions."""

import firebase_admin
from firebase_admin import credentials, firestore
import google.cloud.exceptions
from secrets import token_bytes
from discord.ext import commands

from iam.log import new_logger

LOG = None
"""Logger for this module."""

COG_NAME = "Database"
"""Name of this module's cog."""

CERTIFICATE_FILE = "config/firebase_credentials.json"
"""Location of Firebase certificate file."""

COL_MEMBERS = "members"
"""Name of member collection in database."""

COL_SECRETS = "secrets"
"""Name of secrets collection in database"""

def setup(bot):
    """Add Database cog to bot and set up logging.

    Args:
        bot: Bot object to add cog to.
    """
    global LOG
    LOG = new_logger(__name__)
    LOG.debug(f"Setting up {__name__} extension...")
    cog = Database()
    LOG.debug(f"Initialised {COG_NAME} cog")
    bot.add_cog(cog)
    LOG.debug(f"Added {COG_NAME} cog to bot")

def teardown(bot):
    """Remove Database cog from this bot and remove logging.

    Args:
        bot: Bot object to remove cog from.
    """
    LOG.debug(f"Tearing down {__name__} extension...")
    bot.remove_cog(COG_NAME)
    LOG.debug(f"Removed {COG_NAME} cog from bot")
    for handler in LOG.handlers:
        LOG.removeHandler(handler)

class MemberNotFound(Exception):
    """Member not found in database.

    Attributes:
        member_id: Integer representing Discord ID of member queried.
        context: String containing any additional context related to this
                    exception being thrown.
    """
    def __init__(self, member_id, context):
        """Init exception with given args.

        Args:
            member_id: Integer representing Discord ID of member queried.
            context: String containing any additional context related to this
                     exception being thrown.
        """
        self.member_id = member_id
        self.context = context

    def def_handler(self):
        """Default handler for this exception.

        Log an error message containing relevant context.
        """
        LOG.error(f"Member '{self.member_id}' could not be found in database! "
            f"Context: '{self.context}'")

class MemberKey():
    """Keys for member entries in database."""
    STATE = "_state"
    NAME = "full_name"
    ZID = "zid"
    EMAIL = "email"
    EMAIL_VER = "email_verified"
    ID_MESSAGE = "id_message"
    ID_VER = "id_verified"

class SecretID():
    """Names for secret entries in database."""
    VERIFY = "verify"

class Database(commands.Cog):
    """Handle database functions.
    
    Attributes:
        db: Connected Firestore Client.
    """
    def __init__(self):
        """Init cog and connect to Firestore."""
        LOG.debug(f"Initialising {COG_NAME} cog...")
        self.db = firestore_connect()

    def get_member_data(self, id):
        """Retrieve entry for member in database.

        Args:
            id: Discord ID of member.
        
        Returns:
            Dict containing keys and values associated with member.
        
        Raises:
            MemberNotFound: If member does not exist in database.
        """
        LOG.debug(f"Retrieving member '{id}' from database...")
        data = self._get_member_doc(id).get().to_dict()
        if data is None:
            LOG.warning(f"Failed to retrieve member '{id}' from database - "
                "they do not exist")
            raise MemberNotFound
        LOG.debug(f"Retrieved member '{id}' from database")
        return data

    def get_unverified_members_data(self):
        """Retrieve entries for all unverified members in database.

        Returns:
            Dict where each key is member ID and each value is info associated
            with that member.
        """
        unverified = {}
        docs = self._get_members_col() \
            .where(MemberKey.ID_VER, "==", False).stream()
        for doc in docs:
            member_id = int(doc.id)
            member_data = doc.to_dict()
            unverified[member_id] = member_data
        return unverified

    def set_member_data(self, id, info):
        """Write entry for member to database.
        
        If entry already exists, replace it.

        Args:
            id: Discord ID of member.
            info: Dict of keys and values to write.
        """
        LOG.debug(f"Writing entry for member '{id}' in database: {info}...")
        self._get_member_doc(id).set(info)
        LOG.debug(f"Wrote entry for member '{id}' in database: {info}")

    def update_member_data(self, id, info, must_exist=True):
        """Update entry for member in database.
        
        Will only modify given keys and values. If key does not already exist,
        it will be created.

        By default, will raise exception if member does not exist in database.

        Args:
            id: Discord ID of member.
            info: Dict of keys and values to write.
            must_exist: Boolean for if member must exist in database. If False,
                        will create new entry if they do not.

        Raises:
            MemberNotFound: If member does not exist in database and
                            must_exist == True.
        """
        try:
            self._get_member_doc(id).update(info)
            LOG.debug(f"Updated member '{id}' in database. Patch: {info}")
        except google.cloud.exceptions.NotFound:
            LOG.warning(f"Failed to update member '{id}' entry in database - "
                "they do not exist")
            raise MemberNotFound

    def delete_member_data(self, id, must_exist=True):
        """Delete entry for member in database.

        By default, will raise exception if member does not exist in database.

        Args:
            id: Discord ID of member.
            must_exist: Boolean for if member must exist in database. If False,
                will not raise exception if they don't.

        Raises:
            MemberNotFound: If member does not exist in database and
                            must_exist == True.
        """
        LOG.debug(f"Deleting member '{id}' from database...")
        doc = self._get_member_doc(id)
        if must_exist and doc.get().to_dict() is None:
            LOG.warning(f"Failed to delete member '{id}' in database - they do "
                "not exist")
            raise MemberNotFound
        doc.delete()
        LOG.debug(f"Deleted member '{id}' from database")

    def get_secret(self, id):
        """Retrieve entry for secret from database.

        If no such secret exists, generate one.
        
        Args:
            id: ID of secret.

        Returns:
            Secret bytes associated with id.
        """
        LOG.debug(f"Retrieving '{id}' secret from Firebase")
        doc = self._get_secrets_col().document(str(id))
        data = doc.get().to_dict()
        
        if data is not None:
            secret = data["secret"]
            LOG.debug(f"Retrieved '{id}' secret from Firebase")
        else:
            LOG.info(f"Generating new '{id}' secret...")
            secret = token_bytes(64)
            doc.set({"secret": secret})
            LOG.info(f"Saved new '{id}' secret in Firebase")
        
        return secret
    
    def _get_member_doc(self, id):
        """Retrieve member doc from database.

        Args:
            id: Discord ID of member.

        Returns:
            Firestore document associated with member.
        """
        return self._get_members_col().document(str(id))

    def _get_members_col(self):
        """Get members collection.

        Returns:
            Firestore collection of members.
        """
        return self.db.collection(COL_MEMBERS)
    
    def _get_secrets_col(self):
        """Get secrets collection.

        Returns:
            Firestore collection of secrets.
        """
        return self.db.collection(COL_SECRETS)

def firestore_connect():
    """Connect to Firestore.
    
    Required for all other methods to function.

    Returns:
        Firestore client object.
    """
    LOG.debug("Logging in to Firebase...")
    cred = credentials.Certificate(CERTIFICATE_FILE)
    firebase_admin.initialize_app(cred)
    client = firestore.client()
    LOG.info("Logged in to Firebase")
    return client
