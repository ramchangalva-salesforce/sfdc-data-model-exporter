"""Data models and type definitions."""
from typing import Dict, List, Optional, TypedDict
from datetime import datetime


class ProcessData(TypedDict, total=False):
    """Process data structure."""
    status: str
    logs: List[str]
    created_at: str
    metadata_file: Optional[str]
    lucid_file: Optional[str]
    error: Optional[str]
    has_metadata_file: bool
    metadata_filename: Optional[str]
    has_lucid_file: bool
    lucid_filename: Optional[str]


class SalesforceCredentials(TypedDict):
    """Salesforce authentication credentials."""
    client_id: str
    client_secret: str
    username: str
    password: str
    instance_url: str


class TokenResponse(TypedDict):
    """Salesforce OAuth token response."""
    access_token: str
    instance_url: str
    id: str
    token_type: str
    issued_at: str
    signature: str


class SalesforceObject(TypedDict):
    """Salesforce object metadata."""
    name: str
    label: str
    custom: bool
    keyPrefix: Optional[str]
    labelPlural: Optional[str]


class SalesforceField(TypedDict, total=False):
    """Salesforce field metadata."""
    name: str
    type: str
    length: Optional[int]
    precision: Optional[int]
    scale: Optional[int]
    referenceTo: List[str]
    relationshipName: Optional[str]
    nillable: bool
    required: bool
    unique: bool


class MetadataRow(TypedDict):
    """Metadata CSV row structure."""
    Object: str
    Field: str
    Type: str
    Length: str
    Precision: str
    Scale: str
    ReferenceTo: str
    RelationshipName: str


class LucidRow(TypedDict):
    """Lucidchart CSV row structure."""
    dbms: str
    TABLE_SCHEMA: str
    TABLE_NAME: str
    COLUMN_NAME: str
    ORDINAL_POSITION: int
    DATA_TYPE: str
    CHARACTER_MAXIMUM_LENGTH: str
    CONSTRAINT_TYPE: str
    REFERENCED_TABLE_SCHEMA: str
    REFERENCED_TABLE_NAME: str
    REFERENCED_COLUMN_NAME: str
    COMMENT: str


class SalesforceApp(TypedDict):
    """Salesforce app metadata."""
    id: str
    name: str
    label: str
    namespacePrefix: Optional[str]
    description: Optional[str]

