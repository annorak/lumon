# KC&C source inventory and modeling decisions

Reviewed source decisions as of 2026-09-14.

VALIDATED means Armadin reports exercising the transition. Lumon has not
independently reproduced these attacks. Use the supplied transcripts and
diagrams together, without merging assets or identities across episodes.

This inventory does not establish a path count. Each encoded fixture needs
approved source quotations, entity mappings, intervention effects, and
expected end-to-end path sequences. Pending entries do not enter the demo.

## Sources and encoding status

| Source | Narrated route or report | Encoding status |
|--------|--------------------------|-----------------|
| [Episode 1][ep1] | Web application authentication flaws and SQL injection lead to database-host code execution. | Approved post-login fixture; full external-route dependency unresolved. |
| [Episode 2][ep2] | Auction-site authentication bypass and SQL injection create a privileged account used for Joomla plugin code execution. | Approved two-transition fixture with a two-patch catalog. |
| [Episode 3][ep3], cloud chain | SSRF and an internal API exploit lead through a Kubernetes environment to cloud accounts and production data. | Credential and identity mapping unresolved. |
| [Episode 3][ep3], building-management chain | An assumed corporate foothold leads through PrintNightmare and locally stored credentials to building-management access. | Approved three-transition BMS fixture; dead-end service-account branch excluded. |
| [Episode 4][ep4], Fortune 600 | SSRF and a published CVE lead to credential theft and reported cloud compromise. | Approved fixture contains one reviewed route. |
| [Episode 4][ep4], second engagement | Aggregate findings and validated-path statistics for another organization. | No individual route is described in enough detail to encode. |
| [Episode 4 in depth][ep4-depth] | Further discussion of the Fortune 600 case. | Supporting source, not an additional route. |
| [Episode 5][ep5] | Account registration and SQL injection lead through linked SQL servers to sensitive telecom data. | Approved partial SQL-query fixture; full registration-to-data mapping unresolved. |

## Approved reconnaissance decision for Episodes 1 and 2

Keep Episode 1's source-code disclosure and Episode 2's CLAUDE.md disclosure
in provenance as supporting reconnaissance, outside the severable path.
The sources report that attackers read these files. This placement does
not downgrade those actions to OBSERVED.

The files helped reveal application behavior and vulnerable endpoints.
The sources do not establish that attackers must retrieve them again to
exercise the discovered exploits. Hiding the files must not count as
severing the downstream exploitation route.

Use the diagram's CLAUDE.md spelling when naming the Episode 2 file.
Preserve the supplied transcript's spelling in any approved quotation.

## Approved Episode 1 post-login scope

The [graph](graphs/episode1-post-login.json) starts with reported web access
after admin login. The [provenance](provenance/episode1-post-login.json) keeps
the earlier authentication flaw and source disclosure as supporting history.
This is a separate regression fixture, not part of the Fortune 600 demo input.

The sources do not establish that SQL injection required that login.
This fixture represents only the post-login route, not the full external
route. It does not offer an authentication fix as severing the SQL injection.

The final transition includes enabling database command execution and
using it. Permission reduction must prevent completing that sequence.
Merely disabling a setting the same identity can enable again is insufficient.
Its exact grants and operational effects remain untested.

## Approved Episode 2 auction-site scope

The [graph](graphs/episode2-auction.json) represents authentication bypass
followed by SQL injection and its reported consequences. The final edge
abbreviates privileged-account creation, login, Joomla plugin upload, and
PHP execution. It does not mean direct database-to-operating-system execution.
The [provenance](provenance/episode2-auction.json) cites the full sequence.

The catalog contains only fixes for the authentication bug and SQL injection.
Changing the attacker-created account alone does not establish durable
severance. No separate Joomla vulnerability is reported.
Ingress restrictions, database permissions, and plugin policy are not modeled.

This is a separate regression fixture, not part of the Fortune 600 demo input.

## Episode 3 decisions and unresolved mapping

Keep the cloud chain separate from the building-management chain.

The cloud narrative and diagram describe several credentials and execution
identities without a reviewed mapping between them. Leave those identities
and their relationships unencoded until that mapping is approved. Do not
merge this environment with Episode 4 because the routes look similar.

In the building-management case, credential theft through an antivirus
exclusion folder reached a service-account dead end. It is not a required
step in the successful route through the local building-management database.
Preserve the unsuccessful branch separately in the source record.

The successful narrative ends with building-management access, sensor data,
and visibility into operational-technology networks. Do not extend it to
further operational-technology compromise or physical control.

## Approved Episode 3 building-management scope

The [graph](graphs/episode3-building-management.json) starts with the assumed
contractor foothold. PrintNightmare establishes local administrator control
of the Windows server, where the attacker reads a BMS operator credential
and uses it to log in. SYSTEM execution and account creation remain details
of the exploit, not separate remediation targets.

The catalog contains a PrintNightmare patch at assumed cost 1 and credential
removal at assumed cost 3. Credential removal must eliminate exposed usable
material and invalidate it for BMS login, without leaving an equally readable
usable replacement. Clearing storage alone or rotating the password alone
does not establish both effects. Implementation and BMS compatibility remain
untested, especially while the attacker has host administrator control.

The [provenance](provenance/episode3-building-management.json) keeps the
service-account dead end outside the successful route. Objective weight 5
is assumed. This fixture is separate from the Fortune 600 demo input.

## Approved Fortune 600 scope

The [graph](graphs/episode4-fortune600.json) and
[provenance](provenance/episode4-fortune600.json) record the approved route,
candidate assumptions, and omissions. The shipped
[excerpts](sources/episode4-excerpts.txt) support that mapping.

Extraction tests confirm one reviewed route. That is N for this fixture.
K is the podcast's 12 reported RCE findings. M must come from the minimum-cost
portfolio. It is not a replacement count for those findings, and the solver
does not minimize the number of changes.

The source reports remediation of all 12 findings but does not identify the
customer's implementation changes. Their count, cost, removal effects,
modeled coverage, and remaining access are unknown. The customer bypass
queue is unavailable, not an empty generated queue. Do not claim savings
against the customer's actual changes or that downstream access remained.

Costs and objective weights are assumptions, not measured customer effort
or customer-supplied priorities. Keep the approved catalog and its costs;
do not remove cheap alternatives to force a preferred recommendation.

## Episode 5 decisions and unresolved mapping

Two registration mechanisms and three SQL injections do not establish six
validated end-to-end routes. Do not combine them without reviewed pairings.

The transcript describes five additional SQL servers. The diagram describes
five reachable SQL servers. These may refer to the same linked servers;
the total and exact topology remain unresolved.

The source reports access to workforce information, caller-location data,
and SIM-swap prerequisites. Do not turn access to prerequisites into a
completed SIM-swap attack. The roughly 68.5 million reported rows describe
impact scope, not proof that every row was exfiltrated.

## Approved Episode 5 post-registration scope

The [graph](graphs/episode5-post-registration.json) starts with reported
authenticated application access after registration and token issuance.
It ends at SQL-query execution through one unnamed affected endpoint.
The vulnerability does not combine all three reported SQL injections.

The sole candidate patches the represented injection at assumed cost 1.
It does not establish that one patch fixes all three injections.
Objective weight 5 is assumed. No sensitive-data objective is modeled.

The [provenance](provenance/episode5-post-registration.json) keeps registration
counts, linked-server access, and telecom-data results outside this partial
route. They remain source-reported case details, not invented alternatives.
This fixture is separate from the Fortune 600 demo input.

## Remaining fixture review

Only the Episode 1, Episode 2, Episode 3 building-management, Episode 4,
and Episode 5 fixture excerpts are approved for redistribution. Review the
exact excerpts, graph mappings, path sequences, objective weights, and
intervention applicability before adding other fixtures.
This inventory is not a substitute for their per-path provenance.

[ep1]: https://www.youtube.com/watch?v=6H07KzPNT2w
[ep2]: https://www.youtube.com/watch?v=KPLQmX_dqNM
[ep3]: https://www.youtube.com/watch?v=EIXWUWXRlXs
[ep4]: https://www.youtube.com/watch?v=RxLj-4BsYhg
[ep4-depth]: https://www.youtube.com/watch?v=eFBNNu5zTLk
[ep5]: https://www.youtube.com/watch?v=LXzHIG4CqnA
