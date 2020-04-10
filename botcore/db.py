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

class MemberNotFound(Exception):
    """Member not found in database."""
    pass

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
    CERTIFICATE_FILE = "config/firebase_credentials.json"
    """Location of Firebase certificate file."""

    COL_MEMBERS = "members"
    """Name of member collection in the database."""

    COL_SECRETS = "secrets"
    """Name of secrets collection in the database"""

    def __init__(self):
        """Init cog and connect to Firestore."""
        self.db = None
        self._connect()

    def get_member_data(self, id):
        """Retrieve entry for member in database.

        Args:
            id: Discord ID of member.
        
        Returns:
            Dict containing keys and values associated with member.
        
        Raises:
            MemberNotFound: If member does not exist in database.
        """
        data = self._get_member_doc(id).get().to_dict()
        if data is None:
            raise MemberNotFound
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
        self._get_member_doc(id).set(info)

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
        except google.cloud.exceptions.NotFound:
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
        doc = self._get_member_doc(id)
        if must_exist and doc.get().to_dict() is None:
            raise MemberNotFound
        doc.delete()

    def get_secret(self, id):
        """Retrieve entry for secret from database.

        If no such secret exists, generate one.
        
        Args:
            id: ID of secret.

        Returns:
            Secret bytes associated with id.
        """
        doc = self._get_secrets_col().document(str(id))
        data = doc.get().to_dict()
        
        if data is not None:
            secret = data["secret"]
            print(f"Retrieved '{id}' secret from Firebase")
        else:
            print(f"Generating new '{id}' secret...")
            secret = token_bytes(64)
            doc.set({"secret": secret})
            print(f"Saved {id} secret in Firebase")
        
        return secret

    def _connect(self):
        """Connect to Firestore.
        
        Required for all other methods to function.
        """
        cred = credentials.Certificate(self.CERTIFICATE_FILE)
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        print("Logged in to Firebase")
    
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
        return self.db.collection(self.COL_MEMBERS)
    
    def _get_secrets_col(self):
        """Get secrets collection.

        Returns:
            Firestore collection of secrets.
        """
        return self.db.collection(self.COL_SECRETS)
