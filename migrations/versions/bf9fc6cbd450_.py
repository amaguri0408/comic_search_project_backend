"""empty message

Revision ID: bf9fc6cbd450
Revises: ffe86593ab12
Create Date: 2023-07-18 02:29:39.942305

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'bf9fc6cbd450'
down_revision = 'ffe86593ab12'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('app', schema=None) as batch_op:
        batch_op.alter_column('platform_type',
               existing_type=mysql.ENUM('app', 'web'),
               type_=sa.String(length=20),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('app', schema=None) as batch_op:
        batch_op.alter_column('platform_type',
               existing_type=sa.String(length=20),
               type_=mysql.ENUM('app', 'web'),
               existing_nullable=True)

    # ### end Alembic commands ###
