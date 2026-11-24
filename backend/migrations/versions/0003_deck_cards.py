"""NI-03 deck composition for card counts and color lookup."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "deck_cards",
        sa.Column("deck_id", sa.Integer(), sa.ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("oracle_id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("list_name", sa.String(16), primary_key=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_deck_cards_quantity"),
        sa.CheckConstraint("list_name IN ('main', 'maybeboard')", name="ck_deck_cards_list_name"),
    )


def downgrade():
    op.drop_table("deck_cards")
