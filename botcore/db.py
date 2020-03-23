import firebase_admin
from firebase_admin import credentials, firestore
import google.cloud.exceptions
from secrets import token_bytes
from discord.ext import commands

class MemberNotFound(Exception):
    pass

class MemberKey():
    STATE = "_state"
    NAME = "full_name"
    ZID = "zid"
    EMAIL = "email"
    EMAIL_VER = "email_verified"
    ID_VER = "id_verified"

class SecretID():
    VERIFY = "verify"

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
        
        Raises:
            MemberNotFound: If member does not exist in the database.
        """

        data = self._get_member_doc(id).get().to_dict()
        if data is None:
            raise MemberNotFound
        return data

    def get_unverified_members_data(self):
        """
        Retrieve entries for all unverified members from the database.

        Returns:
            Dictionary where each key is a member ID and each value is the info
            associated with that member.
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
                must_exist == True.
        """

        try:
            self._get_member_doc(id).update(info)
        except google.cloud.exceptions.NotFound:
            raise MemberNotFound

    def delete_member_data(self, id, must_exist=True):
        """
        Delete entry for a member in the database.

        By default, will raise an exception if the member does not exist in the
        database.

        Args:
            id: Discord ID of a member.
            must_exist: If the member must exist in the database. If False,
                will not raise an exception if they don't.

        Raises:
            MemberNotFound: If the member does not exist in the database and
                must_exist == True.
        """

        doc = self._get_member_doc(id)
        if must_exist and doc.get().to_dict() is None:
            raise MemberNotFound
        doc.delete()

    def get_secret(self, id):
        """
        Retrieve entry for a secret from the database.
        If no such secret exists, generate one.
        
        Args:
            id: ID of a secret.

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
