export const DRIVER_FILE_LIMIT = 5 * 1024 * 1024;
export const DRIVER_FIELDS = ['driving_licence', 'vehicle_ownership_proof'];

export function driverRegistrationPayload(form) {
  for (const name of ['vehicle_type', 'registration_reference']) {
    const value = form[name]?.trim();
    if (!value || value.length > 50 || [...value].some(c => c.charCodeAt(0) < 32 || c.charCodeAt(0) === 127)) throw new Error('Enter valid vehicle type and registration number (1–50 characters).');
  }
  for (const name of DRIVER_FIELDS) {
    const file = form[name];
    if (typeof File === 'undefined' || !(file instanceof File) || !file.size) throw new Error('Select both required Driver documents.');
    if (file.size > DRIVER_FILE_LIMIT) throw new Error('Each Driver document must be no larger than 5 MiB.');
    const extension = file.name.split('.').at(-1).toLowerCase();
    const media = { jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', pdf: 'application/pdf' }[extension];
    if (!media || file.type !== media) throw new Error('Driver documents must be JPG, JPEG, PNG or PDF.');
  }
  return { vehicle_type: form.vehicle_type.trim(), registration_reference: form.registration_reference.trim(),
    driving_licence: form.driving_licence, vehicle_ownership_proof: form.vehicle_ownership_proof };
}
