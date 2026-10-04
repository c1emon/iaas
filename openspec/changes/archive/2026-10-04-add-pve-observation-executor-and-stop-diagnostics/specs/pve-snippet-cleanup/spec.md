## ADDED Requirements

### Requirement: Snippet verification observes without repeating helper mutations
Snippet upload and cleanup SHALL dispatch each admitted create/delete operation once and use bounded read-only inspection of its exact file identity, content digest, applicable inode and complete reference scope to verify the intended state. Declared temporary view synchronization and admitted read failures SHALL use the original applicable deadline. Content/identity conflict, foreign reference or insufficient visibility SHALL stop the affected operation. Lost helper responses SHALL retain unknown historical outcome and activity; a new inspection SHALL NOT prove remote helper termination.

#### Scenario: Upload response arrived before complete verification
- **WHEN** the original create operation is known completed but an admitted read-only inspection is temporarily unavailable or not synchronized
- **THEN** the runtime SHALL retry only inspection within the original window
- **AND** it SHALL NOT repeat upload or overwrite the file

#### Scenario: Delete is complete but absence view lags
- **WHEN** deletion is known completed and the first permitted file/reference view is stale
- **THEN** the runtime SHALL recheck the original exact identities under the original deadline without another unlink or delete helper dispatch

#### Scenario: Changed file or unresolved helper activity
- **WHEN** digest/inode conflicts, another object references the file, or a timed-out helper has unresolved activity
- **THEN** the runtime SHALL retain failed/unknown evidence as appropriate and refuse further mutation
- **AND** it SHALL NOT use current file absence as proof of original helper inactivity or historical deletion success
