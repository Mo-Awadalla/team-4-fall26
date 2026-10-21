"""Record whether a cafe has sidewalk seating.

This column is the surviving half of Dining Out NYC. The importer used to treat
an outdoor-dining licence as the definition of a cafe, which published 1,652
spots whose only established property was that they put tables on the pavement
-- bars, pizzerias and restaurants among them. The ``cafe`` category now comes
from the health department's own ``Coffee/Tea`` classification, and the licence
register is read for this one attribute instead.

Unlike 0006 and 0007 this is a plain AddField: the column is not part of
``search_vector``, so Django's refusal to alter a GeneratedField does not apply
and the vector is left alone. A boolean is not something anyone types into a
search box.

No index either, for the same reason as no filter: this is an attribute the API
reports, not one it narrows on. ``free_public_wifi`` and ``no_purchase_needed``
each have an index because each has a query parameter behind it. Adding one here
would be indexing a column nothing queries.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("spots", "0008_cost_is_stored"),
    ]

    operations = [
        migrations.AddField(
            model_name="studyspot",
            name="outdoor_seating",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Whether a current Dining Out NYC sidewalk licence matches this "
                    "establishment's name and address. False means no licence matched, not "
                    "that there is nowhere to sit outside: the join requires both the name "
                    "and the address to agree, because matching on address alone credits a "
                    "cafe with the licence of whichever other business shares its building. "
                    "Only cafes can carry it -- nothing licenses a library to put tables on "
                    "the pavement."
                ),
            ),
        ),
    ]
