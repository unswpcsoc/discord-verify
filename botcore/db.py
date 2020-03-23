import firebase_admin
from firebase_admin import credentials, firestore
import google.cloud.exceptions

from discord.ext import commands

class MemberNotFound(Exception):
    pass

class Database(commands.Cog):
    CERTIFICATE_FILE = "config/firebase_credentials.json"
    COL_MEMBERS = "members"
    COL_SECRETS = "secrets"

    def __init__(self, bot):
        self.bot = bot
        self.db = None
        self._connect()

    def get_member_data(self, id):
        """
        Retrieve entry for a member from the database.

        Args:
            id: Discord ID of a member.
        
        Returns:
            Dictionary containing all keys and values associated with a member.
        """

        return self._get_member_doc(id).get().to_dict()

    def get_unverified_members_data(self):
        """
        Retrieve entries for all unverified members from the database.

        Returns:
            Dictionary where each key is a member ID and each value is the info
            associated with that member.
        """

        unverified = {}
        docs = self._get_members_col() \
            .where("id_verified", "==", False).stream()
        for doc in docs:
            member_id = int(doc.id)
            member_data = doc.to_dict()
            unverified[member_id] = member_data
        return unverified

    def set_member_data(self, id, info):
        """
        Write entry for a member to the database. If entry already exists, will
        replace it.

        Args:
            id: Discord ID of a member.
            info: Dictionary of keys and values to write.
        """

        self._get_member_doc(id).set(info)

    def update_member_data(self, id, info, must_exist=True):
        """
        Update entry for a member in the database. Will only modify given keys
        and values. If a key does not already exist, it will be created.

        By default, will raise an exception if the member does not exist in the
        database.

        Args:
            id: Discord ID of a member.
            info: Dictionary of keys and values to write.
            must_exist: If the member must exist in the database. If False,
                will create a new entry if they do not.

        Raises:
            MemberNotFound: If the member does not exist in the database and
                must_exist == False.
        """

        try:
            self._get_member_doc(id).update(info)
        except google.cloud.exceptions.NotFound:
            raise MemberNotFound

    def get_secret(self, id):
        """
        Retrieve entry for a secret from the database.
        
        Args:
            id: ID of a secret.

        Returns:
            Secret bytes associated with id or None if no such secret exists.
        """

        try:
            return self._get_secrets_col().document(str(id)).get() \
                .to_dict()["secret"]
        except KeyError:
            return None

    def set_secret(self, id, bytes):
        """
        Writes entry for a secret with given id and value bytes to the
        database.

        Args:
            id: ID of a secret, to be used as a key.
            bytes: Value to be associated with id.
        """

        self._get_secrets_col().document(str(id)).set({id: bytes})

    def _connect(self):
        """
        Connect to Firestore. Required for all other methods to function.
        """

        cred = credentials.Certificate(self.CERTIFICATE_FILE)
        firebase_admin.initialize_app(cred)
        self.db = firestore.client()
        print("Logged in to Firebase")
    
    def _get_member_doc(self, id):
        """
        Retrieve entry from .

        Args:
            id: Discord ID of a member.

        Returns:
            Return Firestore document associated with a member.
        """

        return self._get_members_col().document(str(id))

    def _get_members_col(self):
        """
        Retrieves all entries from the members collection.

        Returns:
            Firestore collection of members.
        """

        return self.db.collection(self.COL_MEMBERS)
    
    def _get_secrets_col(self):
        """
        Retrieves all entries from the secrets collection.

        Returns:
            Firestore collection of secrets.
        """

        return self.db.collection(self.COL_SECRETS)
