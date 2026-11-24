import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import { createServer } from 'vite';
import { driverRegistrationPayload } from '../src/utils/driverRegistration.js';
import { createRegistrationController } from '../src/utils/registration.js';

const fields = () => ({ full_name: 'Fictional Driver', email: 'fictional@example.com', password: 'fictional-password-123', preferred_language: 'en',
  vehicle_type: 'Bike', registration_reference: 'FICTIONAL-123',
  driving_licence: new File(['fictional'], 'licence.jpeg', { type: 'image/jpeg' }),
  vehicle_ownership_proof: new File(['fictional'], 'ownership.pdf', { type: 'application/pdf' }) });

test('Driver-only validation rejects missing, oversized, invalid types and vehicle fields', () => {
  assert.equal(driverRegistrationPayload(fields()).vehicle_type, 'Bike');
  for (const patch of [{ driving_licence: null }, { vehicle_ownership_proof: null }, { vehicle_type: '' },
    { registration_reference: 'x\ny' }, { driving_licence: new File(['bad'], 'x.exe', { type: 'image/png' }) },
    { driving_licence: new File(['bad'], 'x.png', { type: 'application/pdf' }) },
    { driving_licence: new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'x.png', { type: 'image/png' }) }]) {
    assert.throws(() => driverRegistrationPayload({ ...fields(), ...patch }));
  }
});

test('basic registration dispatches without documents; duplicate clicks share one operation; uncertain results stop resubmission', async () => {
  let calls = 0;
  const controller = createRegistrationController({ role: 'driver', services: { driver: async () => { calls++; throw new Error('network'); } }, onSuccess() { assert.fail(); }, errorMessage: () => 'Failed' });
  const values = fields();
  for (const [key, value] of Object.entries(values)) if (!['driving_licence', 'vehicle_ownership_proof'].includes(key)) controller.update(key, value);
  controller.update('confirmPassword', values.password);
  controller.update('driving_licence', values.driving_licence); controller.update('vehicle_ownership_proof', values.vehicle_ownership_proof);
  const first = controller.submit(); assert.equal(controller.submit(), first); await first;
  assert.equal(controller.getSnapshot().uncertain, true); await controller.submit(); assert.equal(calls, 1);
  controller.selectRole('customer'); assert.equal(controller.getSnapshot().form.driving_licence, undefined);
});

test('basic registration layout excludes vehicle fields and files in all languages', async () => {
  const server = await createServer({ logLevel: 'silent', appType: 'custom', server: { middlewareMode: true, hmr: false } });
  try {
    const { default: Form } = await server.ssrLoadModule('/src/pages/auth/RegistrationForm.jsx');
    const { createAppI18n } = await server.ssrLoadModule('/src/i18n/index.js');
    for (const language of ['en', 'ta', 'si']) {
      const controller = createRegistrationController({ role: 'driver', services: {}, onSuccess() {}, errorMessage() {} });
      for (const [key, value] of Object.entries(fields())) controller.update(key, value);
      const i18n = createAppI18n({ language });
      const render = () => renderToStaticMarkup(h(I18nextProvider, { i18n }, h(MemoryRouter, null, h(Form, { controller }))));
      const html = render();
      assert.equal((html.match(/type="file"/g) || []).length, 0); assert.ok(!html.includes('ownership.pdf'));
      assert.ok(!html.includes('name="vehicle_type"')); assert.ok(!html.includes('name="registration_reference"'));
      if (language !== 'en') {
        for (const key of ['Driving Licence *', 'Vehicle Ownership Proof *', 'Select both required Driver documents.', 'Each Driver document must be no larger than 5 MiB.', 'Driver documents must be JPG, JPEG, PNG or PDF.']) assert.notEqual(i18n.t(key, { ns: 'application', keySeparator: false }), key);
      }
      controller.selectRole('customer'); assert.ok(!render().includes('type="file"'));
      controller.selectRole('shop-owner'); assert.ok(!render().includes('type="file"'));
    }
  } finally { await server.close(); }
});

test('My Vehicle owns the required file form and exposes honest onboarding states', async () => {
  const server = await createServer({ logLevel: 'silent', appType: 'custom', server: { middlewareMode: true, hmr: false } });
  try {
    const { DriverVehicleView } = await server.ssrLoadModule('/src/pages/driver/DriverVehicle.jsx');
    const { createAppI18n } = await server.ssrLoadModule('/src/i18n/index.js');
    for (const language of ['en','ta','si']) {
      const i18n = createAppI18n({language});
      for (const status of ['not_registered','pending','approved','rejected']) {
        const profile = {driver_user_id:7, approval_status:status==='not_registered'?'not_submitted':status,
          vehicle_registration_status:status,vehicle:null,eligibility_reason:'profile_required'};
        const html = renderToStaticMarkup(h(I18nextProvider,{i18n},h(DriverVehicleView,{profile,onSubmitted(){}})));
        assert.equal((html.match(/type="file"/g)||[]).length,['not_registered','rejected'].includes(status)?2:0);
        assert.ok(!html.includes('undefined'));
        assert.ok(!html.includes('??'));
      }
      if(language!=='en') assert.notEqual(i18n.t('Register Vehicle',{ns:'application',keySeparator:false}),'Register Vehicle');
    }
  } finally {await server.close();}
});
