## 1. NIC platform constraint

- [x] 1.1 Constrain explicit NIC names to the Linux interface-name maximum while preserving the existing character policy.
- [x] 1.2 Document that explicit NIC names become cloud-init guest interface names.

## 2. Regression coverage

- [x] 2.1 Add tests for the 15-character accepted boundary and rejected overlength names.
- [x] 2.2 Run the focused inventory test suite and generated-output check.

## 3. Change validation

- [x] 3.1 Run strict OpenSpec validation for this change and the repository.
- [x] 3.2 Run the repository offline validation gate.
