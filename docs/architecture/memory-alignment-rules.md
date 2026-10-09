# WGSL Memory Alignment and Buffer Layout Rules

> **Scope:** Shader Alchemist's rules for constructing, validating, and evaluating host-shareable WGSL data layouts used by WebGPU uniform and storage buffers.
>
> **Normative reference:** [WebGPU Shading Language (WGSL), Memory Layout and Address Space Layout Constraints](https://www.w3.org/TR/WGSL/).
>
> **Implementation principle:** Never assume that WGSL buffer layout is universally equivalent to GLSL \`std140\`, GLSL \`std430\`, a Rust/C struct layout, or the packing of a JavaScript object. Compute the layout from the WGSL type, its attributes, its address space, and the target's relevant limits/features.

## 1. Why alignment is a correctness rule

A WebGPU buffer is a byte sequence. The host writes bytes into that sequence, and the shader interprets those bytes according to the WGSL type declaration. Neither side automatically repairs a disagreement in field offsets, padding, array stride, or matrix orientation.

A layout mismatch can produce plausible but incorrect values, broken transforms, corrupted indices, out-of-bounds accesses, validation failures, or misleading benchmark results. Shader Alchemist must therefore treat layout as part of the shader's mathematical contract, not as an afterthought or a performance-only hint.

### 1.1 The host-to-shader contract

\`\`\`mermaid
flowchart LR
    A["Logical values / MathSpec"] --> B["WGSL type and address space"]
    A --> C["Host-side encoder"]
    B --> D["WGSL layout calculator"]
    C --> E["Byte buffer"]
    D --> F["Expected offsets, sizes, strides"]
    E --> G["GPU binding"]
    F --> H["Layout validation"]
    G --> H
    H --> I{"Contract agrees?"}
    I -->|Yes| J["Execute shader"]
    I -->|No| K["Reject or repair layout"]
    J --> L["Compare output with reference"]
\`\`\`

The host encoder and shader declaration are two descriptions of the same memory contract. A valid shader alone does not prove that the host encoded the data correctly. Likewise, a correctly packed host buffer cannot make an invalid WGSL declaration valid.

### 1.2 Three separate alignment layers

Do not collapse the following into one rule:

1. **Type/member layout:** byte offsets and padding inside a WGSL structure, array, or matrix.
2. **Binding placement:** the offset and size of a buffer binding, including dynamic-offset alignment limits.
3. **Execution synchronization:** ordering and visibility of accesses between invocations, workgroups, or shader stages.

This document focuses on the first two. Alignment does not itself synchronize memory, and a barrier does not repair a mispacked buffer.

## 2. Terminology and mathematical operators

All sizes and offsets below are measured in **bytes**, where one byte is eight bits.

| Symbol | Meaning |
|---|---|
| \`AlignOf(T)\` | Natural alignment of WGSL type \`T\`. |
| \`SizeOf(T)\` | WGSL memory size of type \`T\`, including any padding that is part of its size. |
| \`AlignOfMember(S, i)\` | Effective alignment of member \`i\` in structure \`S\`, after applicable attributes. |
| \`OffsetOfMember(S, i)\` | Byte offset of member \`i\` from the start of \`S\`. |
| \`StrideOf(array<T>)\` | Distance in bytes between the starts of consecutive array elements. |
| \`SizeOf(S)\` | Total rounded size of a structure \`S\`. |
| \`AS\` | Address space, such as \`uniform\` or \`storage\`. |
| \`RequiredAlignOf(T, AS)\` | Address-space-specific required alignment for type \`T\`. |

### 2.1 Round-up to an alignment

For a non-negative byte offset \(x\) and positive alignment \(a\), define:

\[
\operatorname{roundUp}(a,x)=\left\lceil\frac{x}{a}\right\rceil a
\]

For the power-of-two alignments used by WGSL types, an equivalent integer expression is:

\[
\operatorname{roundUp}(a,x)=(x+a-1)\ \&\ \sim(a-1)
\]

Use the bitwise form only when \`a\` is a positive power of two and the integer width cannot overflow. The ceiling form is the clearer specification-level definition.

Examples:

\[
\operatorname{roundUp}(4,5)=8,\quad
\operatorname{roundUp}(16,20)=32,\quad
\operatorname{roundUp}(16,32)=32
\]

### 2.2 Padding

If the current cursor is \(c\), and the next member requires alignment \(a\), the next member begins at:

\[
o=\operatorname{roundUp}(a,c)
\]

The padding before the member is:

\[
p=o-c
\]

Padding bytes are part of the layout, not useful application fields. The host encoder must place each value at its calculated offset rather than serializing fields consecutively without gaps.

## 3. Core WGSL type layout

The following common host-shareable types have these natural alignment and size values under the WGSL memory-layout rules. Always validate the exact type against the current specification and implementation.

| WGSL type | \`AlignOf(T)\` | \`SizeOf(T)\` | Notes |
|---|---:|---:|---|
| \`i32\`, \`u32\`, \`f32\` | 4 | 4 | Scalar |
| \`f16\` | 2 | 2 | Requires applicable shader/device support |
| \`vec2<f32>\` | 8 | 8 | Two scalar components |
| \`vec3<f32>\` | 16 | 12 | Alignment is 16, stored component size is 12 |
| \`vec4<f32>\` | 16 | 16 | Four scalar components |
| \`vec2<f16>\` | 4 | 4 | Two half-precision components |
| \`vec3<f16>\` | 8 | 6 | Alignment is 8, component size is 6 |
| \`vec4<f16>\` | 8 | 8 | Four half-precision components |

The table is not a license to infer every type's layout from its component count. In particular, matrices are laid out as columns, and arrays use a stride rather than merely the payload size of an element.

### 3.1 The \`vec3<f32>\` rule

A three-component 32-bit vector has a natural alignment of 16 bytes, but a size of 12 bytes. These are different properties.

\`\`\`text
vec3<f32>, starting at byte 0

Byte:   0   1   2   3 | 4   5   6   7 | 8   9  10  11
        x   x   x   x | y   y   y   y | z   z   z   z
Payload: 12 bytes
Natural alignment: 16 bytes
\`\`\`

The next member of a structure is placed using that next member's alignment and the current end cursor. Therefore a following \`f32\` can occupy byte offset 12 in a storage-layout structure after a \`vec3<f32>\`, but a following \`vec4<f32>\` must begin at a 16-byte boundary. In arrays, the vector's stride is rounded up to a multiple of its alignment, so an array of \`vec3<f32>\` has a 16-byte stride.

This distinction is a frequent source of host/shader mismatches. Do not universally add four bytes immediately after every \`vec3\`; compute the next offset from the next member's alignment and the enclosing address-space constraints.

### 3.2 Arrays

For an array element type \(T\), the baseline stride calculation is:

\[
\operatorname{StrideOf}(\operatorname{array}<T>)=
\operatorname{roundUp}(\operatorname{AlignOf}(T),\operatorname{SizeOf}(T))
\]

The array's total size for a fixed element count \(N\) is:

\[
\operatorname{SizeOf}(\operatorname{array}<T,N>)=
N\cdot\operatorname{StrideOf}(\operatorname{array}<T>)
\]

Examples in a storage-layout context:

| Element type | Element size | Element alignment | Stride |
|---|---:|---:|---:|
| \`f32\` | 4 | 4 | 4 |
| \`vec2<f32>\` | 8 | 8 | 8 |
| \`vec3<f32>\` | 12 | 16 | 16 |
| \`vec4<f32>\` | 16 | 16 | 16 |

An element's payload size is not always its array stride. Indexing an array uses the stride:

\[
\operatorname{address}(A[i])=\operatorname{base}(A)+i\cdot\operatorname{StrideOf}(A)
\]

### 3.3 Matrices

WGSL matrices are column-major. A matrix \`matCxR<T>\` contains \(C\) column vectors, each with \(R\) components. Its memory layout follows the layout of an array of those column vectors.

\[
\operatorname{AlignOf}(\operatorname{mat}_{C\times R}<T>)=
\operatorname{AlignOf}(\operatorname{vec}_{R}<T>)
\]

\[
\operatorname{Stride}_{column}=
\operatorname{roundUp}(
\operatorname{AlignOf}(\operatorname{vec}_{R}<T>),
\operatorname{SizeOf}(\operatorname{vec}_{R}<T>)
)
\]

\[
\operatorname{SizeOf}(\operatorname{mat}_{C\times R}<T>)=
C\cdot\operatorname{Stride}_{column}
\]

For example, \`mat3x3<f32>\` has three \`vec3<f32>\` columns. Each column occupies a 16-byte stride, so the matrix has a 48-byte footprint, not a tightly packed 36-byte footprint.

\`\`\`mermaid
flowchart TB
    M["mat3x3<f32>: 48 bytes"] --> C0["Column 0: bytes 0-15"]
    M --> C1["Column 1: bytes 16-31"]
    M --> C2["Column 2: bytes 32-47"]
    C0 --> V0["x, y, z at 0, 4, 8; padding 12-15"]
    C1 --> V1["x, y, z at 16, 20, 24; padding 28-31"]
    C2 --> V2["x, y, z at 32, 36, 40; padding 44-47"]
\`\`\`

The host encoder must also agree on matrix orientation. A transposed interpretation is a semantic mismatch even if the byte count is correct.

## 4. Structure layout algorithm

For a structure with members \(m_0,\ldots,m_{n-1}\), layout proceeds in declaration order. Let \(c_0=0\) be the initial cursor.

For each member \(m_i\) with effective alignment \(a_i\) and effective size \(s_i\):

\[
o_i=\operatorname{roundUp}(a_i,c_i)
\]

\[
c_{i+1}=o_i+s_i
\]

The structure alignment is the maximum effective member alignment:

\[
a_S=\max_i(a_i)
\]

The final structure size is rounded up to the structure alignment:

\[
\operatorname{SizeOf}(S)=\operatorname{roundUp}(a_S,c_n)
\]

This describes the core recursive layout calculation. Address-space rules and member attributes can impose additional requirements; the resulting layout must then be validated for the address space where the type is used.

### 4.1 Worked example: storage structure with a vector

\`\`\`wgsl
struct Particle {
    position: vec3<f32>,
    mass: f32,
    velocity: vec3<f32>,
    id: u32,
}
@group(0) @binding(0)
var<storage, read_write> particles: array<Particle>;
\`\`\`

Under the storage layout rules:

| Member | Alignment | Size | Offset | End |
|---|---:|---:|---:|---:|
| \`position\` | 16 | 12 | 0 | 12 |
| \`mass\` | 4 | 4 | 12 | 16 |
| \`velocity\` | 16 | 12 | 16 | 28 |
| \`id\` | 4 | 4 | 28 | 32 |

The structure alignment is 16 bytes and its size is 32 bytes. Each array element begins 32 bytes after the preceding element.

\`\`\`mermaid
flowchart LR
    subgraph P["Particle: 32 bytes"]
      direction LR
      A["position\\n0-11"] --- B["mass\\n12-15"] --- C["velocity\\n16-27"] --- D["id\\n28-31"]
    end
\`\`\`

Notice why a blanket “every \`vec3\` consumes 16 bytes” rule is misleading: the \`position\` member's next \`f32\` fits into its fourth 4-byte slot in this storage-layout example. The \`velocity\` member is followed by \`id\`, which likewise occupies the final four bytes. The array stride is still 32 bytes because the full structure size is 32.

## 5. Address spaces: storage versus uniform

The WGSL type layout and address-space constraints are related but not interchangeable. A structure that is valid in \`storage\` is not automatically valid in \`uniform\`.

### 5.1 Storage buffers

Storage buffers are commonly used for large arrays, writable data, particle state, generated geometry, and compute-shader input/output. They follow the ordinary WGSL layout requirements for host-shareable types, subject to storage-specific access and resource rules.

For a member with type \(T_i\), its offset must satisfy the applicable required alignment:

\[
\operatorname{OffsetOfMember}(S,i)\bmod
\operatorname{RequiredAlignOf}(T_i,\text{storage})=0
\]

For an array, its stride must satisfy the corresponding element alignment requirements. The exact type's computed stride is used when indexing.

### 5.2 Uniform buffers

Uniform buffers have additional layout constraints. For broad compatibility, Shader Alchemist should validate uniform layouts against the conservative uniform-buffer rules unless the selected device explicitly supports and enables the relevant WGSL feature (currently named \`uniform_buffer_standard_layout\` in the WGSL specification).

Without that feature, two important constraints apply:

1. Array element strides in uniform buffers must be multiples of 16 bytes.
2. When a structure-typed member is followed by another member, the next member must be placed at least \`roundUp(16, SizeOf(nested-struct))\` bytes after the start of that nested structure member.

These are additional to the usual alignment and offset rules. They are not the same thing as saying every field in every uniform buffer is simply laid out according to GLSL \`std140\`.

For a uniform array element \(T\), under the conservative rule:

\[
\operatorname{StrideOf}(\operatorname{array}<T>)\bmod16=0
\]

For a nested structure member \(S\) followed by a member at offset \(o_j\), if the nested structure starts at \(o_i\):

\[
o_j-o_i\geq\operatorname{roundUp}(16,\operatorname{SizeOf}(S))
\]

When the feature is enabled, use the rules in the WGSL specification for that feature rather than applying the conservative rule blindly. Record the device feature set as part of the validation evidence.

### 5.3 Uniform-array example

A tightly packed array of \`f32\` values has a four-byte stride under ordinary array layout. That stride does not satisfy the conservative uniform-buffer array-stride rule.

A wrapper with a 16-byte member size can establish a 16-byte stride:

\`\`\`wgsl
struct UniformF32 {
    @size(16) value: f32,
}

struct Parameters {
    values: array<UniformF32, 8>,
}

@group(0) @binding(0)
var<uniform> params: Parameters;
\`\`\`

Each \`value\` is at the beginning of a 16-byte element; the remaining bytes are padding. This is a correctness-oriented layout, not automatically the most bandwidth-efficient representation. If a packed sequence is required, consider a storage buffer when its semantics and resource constraints fit the workload.

### 5.4 Nested uniform structure example

Under the conservative uniform-buffer rules, a nested structure may need a 16-byte-rounded spacing before a following member. An otherwise plausible declaration can fail validation:

\`\`\`wgsl
struct Inner {
    x: f32,
}

struct InvalidUniform {
    inner: Inner,
    y: f32, // Not enough spacing under conservative uniform rules.
}
\`\`\`

One explicit way to express the required next-member alignment is:

\`\`\`wgsl
struct ValidUniform {
    inner: Inner,
    @align(16) y: f32,
}
\`\`\`

The actual layout must still be calculated and checked. An attribute should not be added mechanically without checking its effect on offsets, structure size, host encoding, and the selected device feature set.

## 6. WGSL attributes that affect layout

### 6.1 \`@align(n)\`

The \`@align(n)\` attribute applies to a structure member and increases or constrains that member's effective alignment. It cannot be used as a casual substitute for understanding the type's natural alignment. The requested value must satisfy the WGSL rules, including the required relationship to the member type's alignment for the relevant address space.

A member's placement is still determined by the normal offset calculation using the effective alignment.

### 6.2 \`@size(n)\`

The \`@size(n)\` attribute on a structure member establishes a minimum member size of \(n\) bytes, subject to WGSL validity rules. It can deliberately create padding and, for arrays of structures with that member, can affect the resulting element stride.

\`@align\` controls where a member may start; \`@size\` controls how much space that member reserves. They solve different problems.

### 6.3 Attributes are part of the interface

The layout calculator must preserve explicit attributes in the schema and generated WGSL. Removing or rewriting an attribute can silently change a buffer contract even if the field names and types remain unchanged.

## 7. Buffer binding offsets and device limits

Correct internal struct layout does not guarantee that a buffer binding is valid. WebGPU has separate device limits governing the alignment of binding offsets, especially for dynamic offsets.

For a dynamic uniform-buffer offset, validate against the selected device's \`minUniformBufferOffsetAlignment\`. For a dynamic storage-buffer offset, validate against \`minStorageBufferOffsetAlignment\`. Query the device limits rather than hardcoding one assumed value.

For binding offset \(o\) and required device alignment \(A\):

\[
o\bmod A=0
\]

Also validate the binding's effective range against the buffer size and the resource binding's size constraints. Do not confuse this device-level binding alignment with \`AlignOf(T)\` or a struct member's offset.

\`\`\`mermaid
flowchart TD
    A["WGSL type layout valid?"] --> B{"Yes"}
    B -->|No| X["Reject shader/layout"]
    B -->|Yes| C["Compute buffer binding range"]
    C --> D["Check binding offset against device limit"]
    D --> E["Check binding size and buffer bounds"]
    E --> F{"All checks pass?"}
    F -->|No| Y["Reject binding or repack"]
    F -->|Yes| G["Create bind group and validate pipeline"]
\`\`\`

## 8. Host-side packing requirements

The CPU representation must be serialized to the exact byte offsets and strides expected by WGSL.

### 8.1 JavaScript and TypeScript

JavaScript objects are logical objects, not GPU buffer layouts. Passing an object such as \`{ position: [x, y, z], mass: m }\` does not make its in-memory object representation suitable for a GPU buffer. Build an \`ArrayBuffer\` or \`TypedArray\` payload deliberately, and write values at offsets computed from the layout contract.

Use \`DataView\` or typed arrays with documented offsets. If using typed arrays, remember that their indexing is based on their own element type and byte offset. Ensure the backing buffer is large enough and any byte-offset requirements are satisfied.

### 8.2 Rust and other systems languages

Do not assume that a Rust \`struct\` with \`repr(C)\` automatically matches every WGSL layout. Language ABI layout, padding, field order, vector types, matrix types, and address-space-specific rules still need to be checked. Prefer an explicit serialization layer or a carefully verified GPU data type representation.

### 8.3 Host packing invariants

For every buffer field \(i\):

\[
\text{hostOffset}_i=\operatorname{OffsetOfMember}(S,i)
\]

For every array element \(j\):

\[
\text{hostElementOffset}_j=\text{arrayBase}+j\cdot\operatorname{StrideOf}(A)
\]

For every matrix column \(k\):

\[
\text{hostColumnOffset}_k=\text{matrixBase}+k\cdot\operatorname{Stride}_{column}
\]

The host must encode the same scalar format, component ordering, matrix orientation, and byte offsets as the WGSL declaration. Keep this layout metadata alongside the generated artifact so that the validator and benchmark harness can independently inspect it.

## 9. Runtime-sized arrays and bounds safety

Runtime-sized arrays are primarily useful for storage-buffer patterns. Their length is determined by the bound buffer range and element stride, not by a compile-time element count in the type declaration.

For a runtime-sized array with effective accessible range \(B\), fixed prefix size \(P\), and element stride \(S\), a simplified upper-bound calculation is:

\[
N=\left\lfloor\frac{B-P}{S}\right\rfloor
\]

Use the actual WGSL type layout and binding range in the implementation; this equation is a planning aid, not a replacement for the WebGPU specification's buffer-binding validation rules.

Every shader index must be checked against the logical element count. A correctly aligned address can still be out of bounds. When dispatch dimensions are rounded up to workgroup sizes, the final partial workgroup must guard accesses:

\[
\text{if } i<N \text{ then access buffer}[i]
\]

Do not infer that a buffer is safe merely because its byte length is divisible by a type's alignment.

## 10. Layout calculation procedure for Shader Alchemist

The layout calculator should be deterministic, inspectable, and independent from the WGSL writer's assumptions.

\`\`\`mermaid
flowchart TD
    A["Parse WGSL / MathSpec types"] --> B["Resolve scalar, vector, matrix, array, struct types"]
    B --> C["Resolve address space and device features"]
    C --> D["Calculate natural AlignOf and SizeOf recursively"]
    D --> E["Apply @align and @size member attributes"]
    E --> F["Calculate member offsets and array/matrix strides"]
    F --> G["Calculate final struct size and alignment"]
    G --> H["Validate address-space constraints"]
    H --> I["Validate binding offsets, ranges, and device limits"]
    I --> J{"Valid?"}
    J -->|No| K["Emit precise diagnostic and candidate repair"]
    J -->|Yes| L["Emit layout manifest"]
    L --> M["Cross-check host encoder and WebGPU harness"]
\`\`\`

### 10.1 Required output manifest

For each buffer type, produce machine-readable metadata similar to the following illustrative JSON. The values must be generated from the actual type, not copied from this example.

\`\`\`json
{
  "type": "Particle",
  "addressSpace": "storage",
  "alignment": 16,
  "size": 32,
  "members": [
    { "name": "position", "type": "vec3<f32>", "offset": 0, "size": 12, "alignment": 16 },
    { "name": "mass", "type": "f32", "offset": 12, "size": 4, "alignment": 4 },
    { "name": "velocity", "type": "vec3<f32>", "offset": 16, "size": 12, "alignment": 16 },
    { "name": "id", "type": "u32", "offset": 28, "size": 4, "alignment": 4 }
  ],
  "arrayStride": 32,
  "validation": {
    "wgslLayoutValid": true,
    "hostLayoutVerified": false,
    "deviceBindingLimitsVerified": false
  }
}
\`\`\`

The final two flags should not be marked true until the host encoder and actual device/binding configuration have been tested. Static WGSL layout validation is not proof of runtime correctness.

### 10.2 Diagnostics should explain the failure

A useful diagnostic states:

- the type, member, or array that failed;
- the computed offset/stride and required alignment;
- the address space and feature assumptions used;
- the relevant WGSL rule;
- a minimal candidate fix, when one can be generated safely;
- whether the fix changes memory footprint or host-side packing.

Example:

\`\`\`text
Layout error: Parameters.samples
  Address space: uniform
  Computed array stride: 4 bytes
  Required stride: a multiple of 16 bytes under the selected uniform-layout rules
  Cause: array<f32, 8> uses a 4-byte element stride
  Candidate: use a valid 16-byte wrapper or redesign the data as a storage buffer
  Follow-up: update host offsets and rerun layout + device validation
\`\`\`

A repair must be treated as a change to the data contract. It is not sufficient to make the shader compile while leaving the host-side bytes unchanged.

## 11. Validation and testing strategy

Use layered checks. A single successful shader compilation is not enough.

| Layer | Checks | Failure examples |
|---|---|---|
| Type/layout calculation | Natural alignments, member offsets, final sizes, array and matrix strides | Wrong \`vec3\` handling; missing struct tail padding |
| Address-space validation | Uniform-specific constraints, storage constraints, nested types | Invalid uniform array stride |
| Host serialization | Actual encoded offsets, byte length, matrix orientation | Host packs fields consecutively |
| Resource binding | Dynamic offset alignment, binding range, buffer size, device limits | Misaligned dynamic offset |
| Shader validation | WGSL parsing, shader module and pipeline creation | Invalid attributes or layout |
| Runtime correctness | Compare output to a CPU/reference implementation; bounds checks | Correctly aligned but wrong index |
| Performance evaluation | Measure representative workloads after correctness passes | “Optimization” changes semantics or benchmark inputs |

### 11.1 Essential test cases

1. Scalars and scalar arrays in storage buffers.
2. \`vec2\`, \`vec3\`, and \`vec4\` fields, including a scalar immediately after a \`vec3\`.
3. Arrays of \`vec3\` and arrays of structures containing \`vec3\`.
4. Rectangular and square matrices, verifying column stride and orientation.
5. Nested structures, including structures used in uniform buffers.
6. Uniform arrays under both conservative baseline rules and feature-enabled rules, where supported.
7. \`@align\` and \`@size\` attributes at valid and invalid values.
8. Runtime-sized storage arrays at zero, one, and multiple elements, including partial workgroups.
9. Binding offsets that are correctly and incorrectly aligned to queried device limits.
10. Host byte payloads that are deliberately malformed to confirm the validator catches the mismatch.

For each positive test, assert exact expected offsets, stride, total size, and host bytes. For each negative test, assert a specific diagnostic category rather than merely expecting “some error”.

## 12. Performance and design trade-offs

Alignment exists to satisfy language and hardware requirements and can also support efficient access. But extra padding increases memory footprint and can reduce cache efficiency or increase transfer volume.

For \(N\) elements with stride \(S\), the total allocation for the array payload is:

\[
B=N\cdot S
\]

If a compact representation uses stride \(S_c\) and a padded representation uses stride \(S_p\), the extra storage is:

\[
\Delta B=N(S_p-S_c)
\]

and the relative increase over the compact representation is:

\[
\text{overhead}=\frac{S_p-S_c}{S_c}\times100\%
\]

Use these equations only when both strides are valid for the same semantic representation and address-space rules. Never remove required padding to reduce bandwidth. Instead, choose a valid type/address-space design and measure it on the target device.

For example, an array of \`vec3<f32>\` with a 16-byte stride spends 4 bytes per element on padding relative to its 12-byte component payload, a 33.3% increase over the payload bytes. This does not mean the representation should be manually packed to 12 bytes: shader-side array indexing and the applicable WGSL layout rules determine the valid stride.

Optimization should compare equivalent workloads, include buffer upload/download costs where relevant, and preserve numerical tolerances and output semantics.

## 13. Rules for agent-generated shaders

The Math Architect, WGSL Writer, Performance Evaluator, and artifact assembler must share one layout contract.

- **Math Architect:** identifies the logical data schema, scalar precision, dimensions, indexing domain, and required host/shader interchange.
- **WGSL Writer:** emits types and address-space declarations consistent with the selected layout manifest. It must not invent offsets based on \`std140\` or \`std430\` assumptions.
- **Layout validator:** calculates offsets, sizes, and strides from WGSL rules and verifies address-space constraints.
- **Host encoder:** consumes the same manifest or an independently checked equivalent when writing bytes.
- **Performance Evaluator:** evaluates only layouts that passed correctness and binding validation, and records padding/footprint details with measurements.
- **Artifact assembler:** packages the WGSL, schema, layout manifest, device features/limits, test results, and benchmark metadata together.

\`\`\`mermaid
flowchart LR
    MA["Math Architect"] --> SC["Typed data contract"]
    SC --> WW["WGSL Writer"]
    SC --> HE["Host encoder"]
    WW --> LV["Layout validator"]
    HE --> HV["Host-byte verification"]
    LV --> RV["Runtime correctness tests"]
    HV --> RV
    RV --> PE["Performance evaluator"]
    PE --> AR["Evidence package"]
    LV -. "layout mismatch" .-> WW
    HV -. "packing mismatch" .-> HE
    RV -. "semantic mismatch" .-> MA
\`\`\`

A layout repair must trigger revalidation of the shader, host encoding, bindings, and correctness tests. If a change affects stride or offsets, prior benchmark results are not directly comparable unless the changed data representation is explicitly recorded.

## 14. Acceptance criteria

A generated buffer layout is considered **validated** only when all applicable conditions hold:

- [ ] Every type has a recursively computed alignment and size.
- [ ] Every structure member has a deterministic byte offset.
- [ ] Every array and matrix has a verified stride.
- [ ] Structure size includes required tail padding.
- [ ] \`@align\` and \`@size\` attributes are included in the calculation.
- [ ] The selected address space's constraints are satisfied.
- [ ] Uniform-buffer feature assumptions are explicit and supported by the device.
- [ ] Buffer binding offsets, sizes, and dynamic-offset limits are valid.
- [ ] Host encoding matches the layout contract byte-for-byte.
- [ ] Runtime bounds and numerical correctness tests pass.
- [ ] Benchmark metadata records the layout manifest and relevant device limits.

A layout may be marked **statically valid** before a device is selected, but it must not be marked **runtime verified** until the relevant WebGPU device and binding checks pass.

## 15. References

1. [W3C WebGPU Shading Language (WGSL) specification](https://www.w3.org/TR/WGSL/) - memory layout, alignment and size, member attributes, address-space constraints.
2. [W3C WebGPU specification](https://www.w3.org/TR/webgpu/) - buffer bindings, resource validation, device limits, and dynamic buffer offsets.
3. [MDN: GPUDevice.limits](https://developer.mozilla.org/en-US/docs/Web/API/GPUDevice/limits) - querying supported WebGPU limits in browser environments.

The normative WGSL and WebGPU specifications take precedence over examples in this document. Update the calculator and tests when the specifications, enabled WGSL features, or supported implementation requirements change.
